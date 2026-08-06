"""Proves FR-1's photo/voice requirement intake against the real Gemini
API -- not a mock. `test_parse_from_synthetic_invoice_image` renders a
real PNG containing pricing/invoice-style text and sends it through the
real Gemini Vision call; `test_parse_from_text_omits_fields_not_present`
proves the "no invented value" acceptance criterion by checking that a
field genuinely absent from the input comes back null, not guessed."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image, ImageDraw

from pact.models.guardrail_client import screen_text_input
from pact.models.requirement_parser import (
    parse_requirement_from_image,
    parse_requirement_from_text,
    transcribe_image_text,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="requires a real GEMINI_API_KEY (FR-1 has no local-fallback path to test against)",
)


def _render_invoice_png(lines: list[str]) -> bytes:
    img = Image.new("RGB", (700, 300), color="white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((20, 20 + i * 30), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_parse_from_synthetic_invoice_image_extracts_real_fields():
    image_bytes = _render_invoice_png(
        [
            "GPU Compute Quote",
            "Spec: 8x H100 GPUs",
            "Contract length: 3 months",
            "Customer budget ceiling: $115,000",
        ]
    )
    result = parse_requirement_from_image(image_bytes, "image/png")
    assert result["gpu_count"] == 8
    assert result["contract_months"] == 3
    assert result["budget_ceiling_usd"] == pytest.approx(115000, rel=1e-6)


def test_parse_from_text_omits_fields_not_present():
    """The input states a GPU count but never a budget -- the real
    acceptance criterion is that budget_ceiling_usd comes back null, not
    an invented number."""
    result = parse_requirement_from_text("We need 4 H100 GPUs for a 6-month contract.")
    assert result["gpu_count"] == 4
    assert result["contract_months"] == 6
    assert result["budget_ceiling_usd"] is None


def test_photo_intake_transcription_reaches_the_same_guardrail_as_text():
    """Closes the gap where photo intake bypassed the Guardrails layer
    entirely: renders a real PNG with a name/email/phone embedded (the
    same PII the guardrail already catches on the text path), transcribes
    it for real via Gemini Vision, and confirms the transcription is real
    enough to trigger the same warning."""
    image_bytes = _render_invoice_png(
        [
            "GPU Compute Quote",
            "Prepared for: John Smith",
            "john.smith@acmecorp.com",
            "Phone: 555-123-4567",
            "Spec: 8x H100 GPUs, 3-month contract",
        ]
    )
    transcript = transcribe_image_text(image_bytes, "image/png")
    assert "john.smith@acmecorp.com" in transcript

    warnings = screen_text_input(transcript)
    pii_warning = next((w for w in warnings if "personal data" in w.lower()), None)
    assert pii_warning is not None
    assert "EMAIL_ADDRESS" in pii_warning
