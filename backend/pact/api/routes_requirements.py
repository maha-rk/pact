"""Requirement intake (PRD FR-1): parses a photographed document or a
spoken-input transcript into structured requirement fields via Gemini.
Never auto-starts a negotiation -- the frontend pre-fills the existing
form with whatever was actually extracted and the user reviews/completes
it before anything is submitted (preserves the human-in-the-loop framing
and the "no invented value" acceptance criterion)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

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


@router.post("/parse-image", response_model=ParsedRequirement)
async def parse_requirement_image(image: UploadFile = File(...)) -> ParsedRequirement:
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported image type: {image.content_type}")
    data = await image.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

    from pact.models.requirement_parser import parse_requirement_from_image

    try:
        fields = parse_requirement_from_image(data, image.content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Requirement parsing unavailable: {exc}") from exc
    return ParsedRequirement(**fields, raw_input=f"[Parsed from uploaded photo: {image.filename}]")


@router.post("/parse-text", response_model=ParsedRequirement)
async def parse_requirement_text(text: str = Form(...)) -> ParsedRequirement:
    if not text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    from pact.models.requirement_parser import parse_requirement_from_text

    try:
        fields = parse_requirement_from_text(text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Requirement parsing unavailable: {exc}") from exc
    return ParsedRequirement(**fields, raw_input=text)
