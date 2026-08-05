"""Gemini narration (PRD §16): Gemini explains a decision already reached
by deterministic logic -- it NEVER determines a price, a verification
verdict, or a compliance verdict. Every fact in its prompt is already
computed; it is constrained to narrate those facts, not invent new ones.
"""

from __future__ import annotations

import os
import time

_MODEL = "gemini-flash-latest"
_MAX_ATTEMPTS = 2
_RETRY_DELAY_SECONDS = 1.0
_TIMEOUT_MS = 10000  # per-attempt hard cap (Google's enforced minimum) --
# narration must never hang the whole negotiation indefinitely (NFR
# "Latency", ~60s end-to-end target, PRD §14)
_client = None


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


def narrate_reasoning(
    selected_vendor: str,
    final_price_usd: float,
    evidence_lines: list[str],
    negotiation_id: str | None = None,
) -> str:
    """Generates the Decision Agent's Reasoning statement (FR-7) from
    already-computed facts. Raises on failure -- callers fall back to the
    deterministic template rather than silently masking the error (NFR
    'Graceful degradation', PRD §27). `negotiation_id`, when supplied,
    correlates this call's real OpenTelemetry span (PRD §23b) to the
    owning negotiation."""
    prompt = (
        "You are the Decision Agent in an autonomous B2B procurement negotiation system. "
        "A negotiation has already concluded with a deterministic, verified, compliant outcome. "
        "Write a concise (2-3 sentence) professional reasoning statement explaining why this "
        "vendor was selected, referencing ONLY the facts given below. Do not invent any number, "
        "percentage, or claim not listed here. Do not use markdown formatting.\n\n"
        f"Selected vendor: {selected_vendor}\n"
        f"Final price: ${final_price_usd:,.2f}\n"
        "Evidence:\n" + "\n".join(f"- {line}" for line in evidence_lines)
    )
    from pact.observability.tracing import traced_model_call

    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with traced_model_call(
                span_name="gemini.narrate_reasoning", model=_MODEL, prompt_text=prompt, negotiation_id=negotiation_id
            ) as span:
                resp = _get_client().models.generate_content(model=_MODEL, contents=prompt)
                span.record_response(resp)
                text = (resp.text or "").strip()
                if not text:
                    raise RuntimeError("Gemini returned an empty response")
                return text
        except Exception as exc:  # transient overload (503) is common and worth one retry
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SECONDS)

    from pact.models.vertex_fallback import generate_via_vertex, vertex_configured

    if vertex_configured():
        try:
            return generate_via_vertex(prompt)
        except Exception:
            pass  # Vertex AI fallback also failed -- raise the original Developer API error below

    raise last_error  # type: ignore[misc]
