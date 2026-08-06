"""Proves the real API Gateway concerns (PRD §23a) actually work -- not
just that the code exists. Two things: real JWT issuance/validation, and
real rate limiting that actually returns 429 once exceeded."""

from __future__ import annotations

import jwt as pyjwt
import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pact.api.gateway import limiter


def test_issued_token_is_a_real_verifiable_jwt(monkeypatch):
    monkeypatch.setenv("PACT_JWT_SECRET", "test-secret")
    # reload so gateway picks up the freshly-set secret rather than one
    # cached from an earlier test's monkeypatch
    import importlib

    import pact.api.gateway as gateway

    importlib.reload(gateway)

    token = gateway.create_access_token(subject="pact-operator")
    decoded = pyjwt.decode(token, "test-secret", algorithms=["HS256"])
    assert decoded["sub"] == "pact-operator"
    assert "exp" in decoded


def test_auth_dependency_is_a_no_op_when_not_required(monkeypatch):
    monkeypatch.delenv("AUTH_REQUIRED", raising=False)
    import asyncio

    import pact.api.gateway as gateway

    asyncio.run(gateway.require_bearer_token(authorization=None))  # must not raise


def test_auth_dependency_rejects_missing_and_bad_tokens_when_required(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("PACT_JWT_SECRET", "test-secret-2")
    import asyncio
    import importlib

    import pact.api.gateway as gateway

    importlib.reload(gateway)

    with pytest.raises(HTTPException):
        asyncio.run(gateway.require_bearer_token(authorization=None))
    with pytest.raises(HTTPException):
        asyncio.run(gateway.require_bearer_token(authorization="Bearer not-a-real-token"))

    good_token = gateway.create_access_token(subject="pact-operator")
    asyncio.run(gateway.require_bearer_token(authorization=f"Bearer {good_token}"))  # must not raise

    monkeypatch.delenv("AUTH_REQUIRED", raising=False)
    importlib.reload(gateway)


def test_rate_limiting_actually_returns_429_once_exceeded():
    """A tiny, isolated app with a 2/minute limit -- proves the real
    mechanism trips, rather than exercising the production 20/minute
    limit end to end (which would need 21 real requests to prove)."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    @limiter.limit("2/minute")
    def ping(request: Request) -> dict:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    third = client.get("/ping")
    assert third.status_code == 429
