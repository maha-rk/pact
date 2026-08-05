"""Requirement intake (PRD FR-1): parses a photographed document or a
spoken-input transcript into structured requirement fields via Gemini.
Never auto-starts a negotiation -- the frontend pre-fills the existing
form with whatever was actually extracted and the user reviews/completes
it before anything is submitted (preserves the human-in-the-loop framing
and the "no invented value" acceptance criterion)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from pact.api.gateway import limiter, require_bearer_token

router = APIRouter(prefix="/requirements", tags=["requirements"])

_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


class ParsedRequirement(BaseModel):
    gpu_type: str | None
    gpu_count: int | None
    contract_months: int | None
    budget_ceiling_usd: float | None
    region: str | None
    raw_input: str
    guardrail_warnings: list[str] = []


@router.post("/parse-image", response_model=ParsedRequirement, dependencies=[Depends(require_bearer_token)])
@limiter.limit("20/minute")
async def parse_requirement_image(request: Request, image: UploadFile = File(...)) -> ParsedRequirement:
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported image type: {image.content_type}")
    data = await image.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

    from pact.models.guardrail_client import screen_text_input
    from pact.models.requirement_parser import parse_requirement_from_image, transcribe_image_text

    # Real verbatim transcription so photo intake gets the same guardrail
    # screen as text/voice intake (PRD §23a) -- best-effort: a failure here
    # never blocks the actual structured extraction below, it just means
    # this run has nothing to screen and falls back to the filename
    # placeholder, same as before this fix.
    raw_input = f"[Parsed from uploaded photo: {image.filename}]"
    warnings: list[str] = []
    try:
        transcript = transcribe_image_text(data, image.content_type)
        if transcript:
            raw_input = transcript
            warnings = screen_text_input(transcript)
    except Exception:
        pass

    try:
        fields = parse_requirement_from_image(data, image.content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Requirement parsing unavailable: {exc}") from exc
    return ParsedRequirement(**fields, raw_input=raw_input, guardrail_warnings=warnings)


@router.post("/parse-text", response_model=ParsedRequirement, dependencies=[Depends(require_bearer_token)])
@limiter.limit("20/minute")
async def parse_requirement_text(request: Request, text: str = Form(...)) -> ParsedRequirement:
    if not text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    from pact.models.guardrail_client import screen_text_input
    from pact.models.requirement_parser import parse_requirement_from_text

    try:
        fields = parse_requirement_from_text(text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Requirement parsing unavailable: {exc}") from exc
    warnings = screen_text_input(text)
    return ParsedRequirement(**fields, raw_input=text, guardrail_warnings=warnings)
