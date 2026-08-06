"""Gemma plausibility pre-screen (PRD §11/§16): a fast, self-hosted,
high-frequency signal that runs BEFORE the deterministic verification
check -- it is its own independent note, never the verdict. The
match/mismatch decision that actually gates the negotiation stays a
plain, deterministic numeric comparison (pact/mcp_tools/verification_tool.py)
-- an LLM never decides that outcome, preserving reproducibility (FR-4)
and the zero-fabricated-numbers guarantee for the number that matters.

Runs against a local Ollama instance -- genuinely self-hosted, not a
hosted API call.
"""

from __future__ import annotations

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"
TIMEOUT_SECONDS = 5.0  # fast, high-frequency screen -- must never slow the negotiation loop


def plausibility_screen(vendor_id: str, claimed_discount_rate: float, contract_months: int) -> str:
    """Returns a short human-readable plausibility note, e.g.
    'SUSPICIOUS: ...' or 'PLAUSIBLE: ...'. Raises on failure -- callers
    treat this as optional/best-effort and continue without it (PRD §27)."""
    prompt = (
        f"A cloud GPU vendor ({vendor_id.upper()}) claims a "
        f"{claimed_discount_rate:.0%} committed-use discount for a "
        f"{contract_months}-month contract. Is this plausible or "
        "suspiciously high for a commitment this short? Answer with one "
        "word (PLAUSIBLE or SUSPICIOUS), a colon, then a one-sentence reason."
    )
    from pact.observability.tracing import traced_model_call

    with traced_model_call(span_name="gemma.plausibility_screen", model=MODEL, prompt_text=prompt) as span:
        resp = httpx.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        prompt_tokens = body.get("prompt_eval_count")
        completion_tokens = body.get("eval_count")
        if prompt_tokens is not None:
            span.set_attribute("tokens.prompt", prompt_tokens)
        if completion_tokens is not None:
            span.set_attribute("tokens.completion", completion_tokens)
        # Ollama reports the two halves but no total, unlike Gemini's
        # usage_metadata -- sum them here so `tokens_total` (the column the
        # observability dashboard actually reads) isn't null for every real
        # Gemma call. Caught for real: 40 successful Gemma calls had prompt
        # and completion tokens logged but showed "tokens: —" on the
        # dashboard because only `tokens.total` was being surfaced.
        if prompt_tokens is not None and completion_tokens is not None:
            span.set_attribute("tokens.total", prompt_tokens + completion_tokens)
        text = (body.get("response") or "").strip()
        if not text:
            raise RuntimeError("Gemma returned an empty response")
        return text
