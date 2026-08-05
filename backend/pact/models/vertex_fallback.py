"""Vertex AI as a real, tested fallback for the two places Pact calls
Gemini (`gemini_client.py`'s decision narration, `requirement_parser.py`'s
FR-1 intake) -- not the default path. The Developer API (a flat API key,
no billing dependency) is deliberately the primary path; this exists
specifically to survive its stricter free-tier rate limit, which this
build has genuinely hit more than once.

Only attempted after the Developer API's own retries are exhausted. If
Vertex AI also fails, or isn't configured (no GCP_PROJECT_ID set),
callers fall through to their existing degradation behavior unchanged --
this can only ever help, never make a failure path worse, since it's
never on the critical path when the primary call succeeds.

Confirmed working with a real call against the pact-hackathon GCP
project (`gemini-2.5-flash` -- Vertex AI's model naming differs from the
Developer API's `gemini-flash-latest` alias) before being wired in here.
"""

from __future__ import annotations

import os

_VERTEX_MODEL = "gemini-2.5-flash"
_VERTEX_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
_vertex_client = None


def vertex_configured() -> bool:
    return bool(os.environ.get("GCP_PROJECT_ID"))


def _get_vertex_client():
    global _vertex_client
    if _vertex_client is None:
        from google import genai

        _vertex_client = genai.Client(
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=_VERTEX_LOCATION,
        )
    return _vertex_client


def generate_via_vertex(contents, config=None) -> str:
    """Raises on failure -- callers already have their own next-tier
    degradation behavior (a deterministic template, or a clean error) and
    should catch this exactly like any other failed attempt."""
    from pact.observability.tracing import traced_model_call

    trace_text = contents if isinstance(contents, str) else "\n".join(c if isinstance(c, str) else "<image>" for c in contents)
    with traced_model_call(span_name="vertex.generate", model=_VERTEX_MODEL, prompt_text=trace_text) as span:
        resp = _get_vertex_client().models.generate_content(model=_VERTEX_MODEL, contents=contents, config=config)
        span.record_response(resp)
        text = (resp.text or "").strip()
        if not text:
            raise RuntimeError("Vertex AI returned an empty response")
        return text
