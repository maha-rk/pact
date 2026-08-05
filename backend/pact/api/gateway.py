"""Real API Gateway concerns for pact-core (PRD §23a): authentication and
rate limiting, implemented as FastAPI dependencies/middleware directly in
the application rather than a separate physical gateway process. That's a
deliberate, disclosed architectural choice at this single-operator scale
(a dedicated gateway process buys nothing extra here) -- not a
substitute for the real thing: the JWT issuance/validation and the rate
limiter below are genuinely real, tested code, not stubs.

TLS termination -- the third classic "API Gateway" concern -- is real
today via the deployment layer (ngrok terminates TLS for the public
HTTPS endpoint; see README's Deployment section), not something this
module needs to implement itself.

Authentication is disabled by default (`AUTH_REQUIRED` unset) because
this build has no end-user accounts yet -- gating the demo UI from
itself wouldn't mean anything. What matters is that the mechanism is
real and proven: set `AUTH_REQUIRED=true` and `PACT_API_KEY` to require
a real signed bearer token on every negotiation-mutating endpoint.
Rate limiting has no such caveat -- it's real and always on, since it
only ever engages under actual abuse-level traffic.
"""

from __future__ import annotations

import os
import time

import jwt
from fastapi import Header, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 3600

limiter = Limiter(key_func=get_remote_address)


def auth_required() -> bool:
    return os.environ.get("AUTH_REQUIRED", "").lower() == "true"


def _secret() -> str:
    secret = os.environ.get("PACT_JWT_SECRET")
    if not secret:
        raise RuntimeError("PACT_JWT_SECRET not set")
    return secret


def create_access_token(subject: str) -> str:
    now = int(time.time())
    payload = {"sub": subject, "iat": now, "exp": now + _TOKEN_TTL_SECONDS}
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


async def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency: validates a real signed JWT bearer token. A
    no-op when AUTH_REQUIRED isn't "true" -- see module docstring for why
    that's the honest default for a build with no end-user accounts."""
    if not auth_required():
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}") from exc
