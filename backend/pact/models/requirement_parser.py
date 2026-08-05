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


def _trace_text(contents: list) -> str:
    """A stable text representation of a possibly-multimodal `contents`
    list, for the tracing span's prompt hash -- image parts aren't text,
    so they're represented by a fixed marker rather than their bytes."""
    return "\n".join(c if isinstance(c, str) else "<image>" for c in contents)


def _generate(contents: list) -> dict:
    from google.genai import types

    from pact.observability.tracing import traced_model_call

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=_RESPONSE_SCHEMA,
    )
    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with traced_model_call(
                span_name="gemini.parse_requirement", model=_MODEL, prompt_text=_trace_text(contents)
            ) as span:
                resp = _get_client().models.generate_content(model=_MODEL, contents=contents, config=config)
                span.record_response(resp)
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


def transcribe_image_text(image_bytes: bytes, mime_type: str) -> str:
    """Verbatim text transcription of a photographed document, used only
    to run the same text-based guardrail screen (PRD §23a) over photo
    intake that already runs over text/voice intake -- closes the gap
    where photo input previously bypassed the Guardrails layer entirely
    (there was no text to screen). A separate, plain-text Gemini call
    from the structured extraction below; its own failure never blocks
    that extraction (caught by the caller)."""
    from google.genai import types

    from pact.observability.tracing import traced_model_call

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    instruction = (
        "Transcribe ALL visible text in this image verbatim, exactly as written. "
        "Do not summarize, interpret, or omit anything. If there is no legible "
        "text, return an empty string."
    )
    contents = [instruction, image_part]

    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with traced_model_call(span_name="gemini.transcribe_image", model=_MODEL, prompt_text=instruction) as span:
                resp = _get_client().models.generate_content(model=_MODEL, contents=contents)
                span.record_response(resp)
                return (resp.text or "").strip()
        except Exception as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SECONDS)

    from pact.models.vertex_fallback import generate_via_vertex, vertex_configured

    if vertex_configured():
        try:
            return generate_via_vertex(contents)
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
