"""Real token issuance (PRD §23a). A pre-shared PACT_API_KEY exchanges
for a short-lived signed JWT -- a legitimate machine-to-machine pattern
for a single-operator build with no end-user account system. Only
meaningful when AUTH_REQUIRED=true (see pact/api/gateway.py); this route
still works either way so the mechanism can be exercised and tested
regardless of whether enforcement is currently switched on."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pact.api.gateway import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


@router.post("/token", response_model=TokenResponse)
def issue_token(req: TokenRequest) -> TokenResponse:
    expected = os.environ.get("PACT_API_KEY")
    if not expected or req.api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return TokenResponse(access_token=create_access_token(subject="pact-operator"))
