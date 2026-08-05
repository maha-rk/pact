"""Self-hosted LLM guardrail layer for FR-1's photo/voice/text requirement
intake (PRD §23a) -- the one place in Pact where raw, unstructured user
input reaches an LLM before any deterministic validation.

Real, live API testing against Enkrypt AI's hosted guardrails (see PRD
§32) found its default detectors missed a crafted prompt-injection
attempt entirely and caught only 1 of 3 real PII items in a test quote.
Side-by-side testing of these two self-hosted alternatives on the exact
same inputs caught everything Enkrypt missed, with no external API,
rate limit, or cost -- so they replace Enkrypt AI here rather than
supplement it.

Like Gemma's plausibility pre-screen (PRD §16), this is independent,
best-effort, and never authoritative: it never blocks or alters the
actual Gemini call. Findings are surfaced to the human who reviews the
pre-filled form before a negotiation starts (PRD §23a, FR-1's
human-in-the-loop framing) -- warning that reviewer is the real value
here, not silently logging to a place nobody looks.
"""

from __future__ import annotations

_INJECTION_MODEL = "protectai/deberta-v3-base-prompt-injection-v2"
_INJECTION_THRESHOLD = 0.5

# Genuinely-personal entity types only -- Presidio's default recognizer
# set also flags things like DATE_TIME and generic URL fragments that are
# noise for this purpose, not identifying information.
_PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD", "IBAN_CODE"]
_PII_SCORE_THRESHOLD = 0.5

_injection_classifier = None
_pii_analyzer = None


def _get_injection_classifier():
    global _injection_classifier
    if _injection_classifier is None:
        from transformers import pipeline

        _injection_classifier = pipeline("text-classification", model=_INJECTION_MODEL)
    return _injection_classifier


def _get_pii_analyzer():
    global _pii_analyzer
    if _pii_analyzer is None:
        from presidio_analyzer import AnalyzerEngine

        _pii_analyzer = AnalyzerEngine()
    return _pii_analyzer


def screen_text_input(text: str) -> list[str]:
    """Best-effort guardrail screen over raw user input before it reaches
    Gemini. Returns a list of human-readable warnings (empty if none) --
    never raises, never blocks the caller; a failure here is swallowed
    and treated as "nothing to report" (PRD §27's degradation discipline
    applied to this layer specifically)."""
    warnings: list[str] = []

    try:
        result = _get_injection_classifier()(text)[0]
        if result["label"] == "INJECTION" and result["score"] >= _INJECTION_THRESHOLD:
            warnings.append(
                f"Possible prompt injection detected in this input "
                f"(confidence {result['score']:.0%}) -- review the extracted fields carefully."
            )
    except Exception:
        pass

    try:
        results = _get_pii_analyzer().analyze(text=text, language="en", entities=_PII_ENTITIES)
        found = sorted({r.entity_type for r in results if r.score >= _PII_SCORE_THRESHOLD})
        if found:
            warnings.append(f"Possible personal data detected in this input: {', '.join(found)}.")
    except Exception:
        pass

    return warnings
