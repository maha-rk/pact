"""Tests pact/logging/bigquery_sink.py's `_maybe_encrypted` helper --
the actual call site that decides whether budget_ceiling_usd,
final_price_usd, and reasoning get encrypted before a real BigQuery
write. No real BigQuery client is needed for this; it's pure logic
around the real field_encryption primitive already proven in
test_field_encryption.py."""

from __future__ import annotations

import base64
import os

import pytest

from pact.logging import bigquery_sink
from pact.security import field_encryption


def test_none_stays_none_regardless_of_key(monkeypatch):
    monkeypatch.delenv("PACT_FIELD_ENCRYPTION_KEY", raising=False)
    assert bigquery_sink._maybe_encrypted(None) is None


def test_without_a_key_configured_falls_back_to_plaintext_with_a_warning(monkeypatch, caplog):
    monkeypatch.delenv("PACT_FIELD_ENCRYPTION_KEY", raising=False)
    with caplog.at_level("WARNING"):
        result = bigquery_sink._maybe_encrypted(115000.0)
    assert result == "115000.0"
    assert any("plaintext" in record.message for record in caplog.records)


def test_with_a_key_configured_the_value_is_really_encrypted(monkeypatch):
    monkeypatch.setenv("PACT_FIELD_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    result = bigquery_sink._maybe_encrypted(115000.0)
    assert result != "115000.0"
    assert field_encryption.decrypt_field(result) == "115000.0"


def test_encrypts_strings_too_not_just_numbers(monkeypatch):
    monkeypatch.setenv("PACT_FIELD_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    reasoning = "Azure selected: verified 81.52% spot discount, compliant with budget policy."
    result = bigquery_sink._maybe_encrypted(reasoning)
    assert reasoning not in result
    assert field_encryption.decrypt_field(result) == reasoning
