"""Real AES-256-GCM round-trip tests for pact/security/field_encryption.py
-- no mocks, the actual cryptography library primitive end to end."""

from __future__ import annotations

import base64
import os

import pytest

from pact.security import field_encryption


@pytest.fixture
def real_key(monkeypatch):
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("PACT_FIELD_ENCRYPTION_KEY", key)
    return key


def test_is_configured_reflects_the_env_var(monkeypatch):
    monkeypatch.delenv("PACT_FIELD_ENCRYPTION_KEY", raising=False)
    assert field_encryption.is_configured() is False
    monkeypatch.setenv("PACT_FIELD_ENCRYPTION_KEY", "anything")
    assert field_encryption.is_configured() is True


def test_encrypt_then_decrypt_round_trips_to_the_original_value(real_key):
    plaintext = "115000.0"
    ciphertext = field_encryption.encrypt_field(plaintext)
    assert ciphertext != plaintext
    assert field_encryption.decrypt_field(ciphertext) == plaintext


def test_ciphertext_is_not_a_substring_of_the_plaintext_and_varies_per_call(real_key):
    """A real nonce means encrypting the same value twice produces
    different ciphertext -- proves this isn't a deterministic hash or a
    no-op passthrough."""
    first = field_encryption.encrypt_field("azure selected at $39,246.20")
    second = field_encryption.encrypt_field("azure selected at $39,246.20")
    assert first != second
    assert "azure" not in first
    assert "39,246" not in first
    assert field_encryption.decrypt_field(first) == "azure selected at $39,246.20"
    assert field_encryption.decrypt_field(second) == "azure selected at $39,246.20"


def test_decrypting_with_the_wrong_key_fails_rather_than_returning_garbage(monkeypatch):
    from cryptography.exceptions import InvalidTag

    monkeypatch.setenv("PACT_FIELD_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    ciphertext = field_encryption.encrypt_field("sensitive reasoning text")

    monkeypatch.setenv("PACT_FIELD_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    with pytest.raises(InvalidTag):
        field_encryption.decrypt_field(ciphertext)


def test_a_non_32_byte_key_is_rejected(monkeypatch):
    monkeypatch.setenv("PACT_FIELD_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(16)).decode())
    with pytest.raises(ValueError, match="32 bytes"):
        field_encryption.encrypt_field("x")
