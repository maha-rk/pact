"""Gemini-based requirement intake (PRD FR-1): extracts a structured
requirement from a photographed document (a quote, invoice, or spec
sheet) or from spoken input already converted to text by the browser.

Strictly bounded per the FR-1 acceptance criterion -- "no field is
populated with an invented value not present in the input": the model is
instructed to omit (null) any field it cannot ground in the actual
image/text, and every returned field is a candidate for the user to
review and correct before a negotiation ever starts, never auto-submitted.
Gemini never determines a price or outcome here -- it only extracts
values already present in what the user gave it, same isolation principle
as narrate_reasoning() (PRD §16)."""

from __future__ import annotations

import json
import os
import time

_MODEL = "gemini-flash-latest"
_MAX_ATTEMPTS = 2
_RETRY_DELAY_SECONDS = 1.0
_TIMEOUT_MS = 10000
_client = None

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "gpu_type": {"type": ["string", "null"]},
        "gpu_count": {"type": ["integer", "null"]},
        "contract_months": {"type": ["integer", "null"]},
        "budget_ceiling_usd": {"type": ["number", "null"]},
        "region": {"type": ["string", "null"]},
    },
    "required": ["gpu_type", "gpu_count", "contract_months", "budget_ceiling_usd", "region"],
}

_INSTRUCTION = (
    "You extract structured procurement requirement fields from the input. "
    "Return ONLY fields whose value is actually present or directly stated in "
    "the input. If a field is not present, absent, illegible, or ambiguous, "
    "return null for it -- NEVER guess, estimate, or invent a plausible-looking "
    "value. gpu_count and contract_months must be whole numbers if present. "
    "budget_ceiling_usd must be a plain number in US dollars if present."
)


def _get_client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)),
        )
    return _client


def _generate(contents: list) -> dict:
    from google.genai import types

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=_RESPONSE_SCHEMA,
    )
    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = _get_client().models.generate_content(model=_MODEL, contents=contents, config=config)
            text = (resp.text or "").strip()
            if not text:
                raise RuntimeError("Gemini returned an empty response")
            return json.loads(text)
        except Exception as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SECONDS)

    from pact.models.vertex_fallback import generate_via_vertex, vertex_configured

    if vertex_configured():
        try:
            return json.loads(generate_via_vertex(contents, config=config))
        except Exception:
            pass  # Vertex AI fallback also failed -- raise the original Developer API error below

    raise last_error  # type: ignore[misc]


def parse_requirement_from_image(image_bytes: bytes, mime_type: str) -> dict:
    """Photographed document -> structured fields (FR-1, second modality)."""
    from google.genai import types

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    return _generate([_INSTRUCTION, image_part])


def parse_requirement_from_text(text: str) -> dict:
    """Free text -- typically a browser speech-to-text transcript of
    spoken input (FR-1, first modality) -- -> structured fields."""
    return _generate([_INSTRUCTION, f"Input text:\n{text}"])
