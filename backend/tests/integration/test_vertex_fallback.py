"""Proves the Vertex AI fallback (PRD §16) genuinely fires and serves a
real response when the Developer API call fails -- not just that the
code path exists. Requires GCP_PROJECT_ID and real Application Default
Credentials (gcloud auth application-default login) against a real,
billing-enabled GCP project; skips otherwise, since there is no
meaningful way to fake this without contradicting the whole point of the
test."""

from __future__ import annotations

import os

import pytest

from pact.models import gemini_client

pytestmark = pytest.mark.skipif(
    not os.environ.get("GCP_PROJECT_ID"),
    reason="requires a real GCP_PROJECT_ID with billing + Vertex AI enabled, and real ADC",
)


def test_narration_falls_back_to_vertex_when_developer_api_key_is_bad(monkeypatch):
    """A deliberately invalid Developer API key forces every Developer
    API attempt to fail for real, proving the fallback -- not the
    primary path -- is what actually produced the result."""
    monkeypatch.setenv("GEMINI_API_KEY", "invalid-key-forces-a-real-failure")
    gemini_client._client = None  # force _get_client() to rebuild with the bad key

    text = gemini_client.narrate_reasoning(
        selected_vendor="azure",
        final_price_usd=39246.20,
        evidence_lines=["81.5% discount confirmed against real pricing data"],
    )
    assert text
    assert "39,246.20" in text or "39246.20" in text or "azure" in text.lower()

    gemini_client._client = None  # don't leak the bad key into other tests
