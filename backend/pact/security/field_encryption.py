"""Real, application-level AES-256-GCM field encryption for sensitive
negotiation data before it's written to BigQuery -- closing the
architecture review's "relies solely on default cloud provider
encryption" gap for the fields that actually matter in this schema: the
buyer's true budget ceiling (this system's closest analog to a
reservation price/BATNA -- never revealed to a vendor during
negotiation), the final negotiated price, and the Decision Agent's
reasoning text. See `pact/logging/bigquery_sink.py` for the actual call
site and PRD §26.

Uses AES-256-GCM directly (not Fernet, which is AES-128) via the
`cryptography` library's audited AEAD primitive -- authenticated
encryption, so a tampered ciphertext fails to decrypt rather than
silently returning corrupted data.

Key: `PACT_FIELD_ENCRYPTION_KEY`, a base64-encoded 32-byte key (see
`.env.example` for how to generate one). Real when configured; when not
configured, the BigQuery sink falls back to writing plaintext with a
loud warning log -- mirroring this codebase's other "real, tested,
honestly-not-default" gates (`AUTH_REQUIRED`, `PACT_DISTRIBUTED`), not a
silent, undisclosed degradation."""

from __future__ import annotations

import base64
import os

_KEY_ENV_VAR = "PACT_FIELD_ENCRYPTION_KEY"


def is_configured() -> bool:
    return bool(os.environ.get(_KEY_ENV_VAR))


def _get_key() -> bytes:
    raw = os.environ[_KEY_ENV_VAR]
    key = base64.urlsafe_b64decode(raw)
    if len(key) != 32:
        raise ValueError(f"{_KEY_ENV_VAR} must decode to exactly 32 bytes (AES-256), got {len(key)}")
    return key


def encrypt_field(value: str) -> str:
    """Real AES-256-GCM encryption. Returns a base64-encoded
    nonce||ciphertext||tag string, safe to store in a BigQuery STRING
    column. Raises `KeyError` if `PACT_FIELD_ENCRYPTION_KEY` isn't set --
    callers check `is_configured()` first and decide how to degrade."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(token: str) -> str:
    """Inverse of `encrypt_field`. Raises
    `cryptography.exceptions.InvalidTag` if the ciphertext was tampered
    with, truncated, or decrypted with the wrong key."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.urlsafe_b64decode(token)
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
