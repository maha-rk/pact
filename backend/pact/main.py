"""Pact core API entrypoint."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # picks up backend/.env (gitignored) -- GEMINI_API_KEY, etc.

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pact.api.gateway import limiter
from pact.api.routes_auth import router as auth_router
from pact.api.routes_negotiation import router as negotiation_router
from pact.api.routes_requirements import router as requirements_router
from pact.observability.tracing import configure_tracing

configure_tracing()  # real OpenTelemetry spans for every Gemini/Gemma call (PRD §23b)

app = FastAPI(title="Pact — Autonomous B2B Procurement Negotiation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Real API Gateway concerns (PRD §23a): rate limiting is always on;
# authentication is enforced per-route via Depends(require_bearer_token),
# a no-op unless AUTH_REQUIRED=true -- see pact/api/gateway.py.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(auth_router)
app.include_router(negotiation_router)
app.include_router(requirements_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Serves the built frontend (frontend/dist) when present -- the deployed
# container's single public entrypoint. In local dev, this directory
# doesn't exist and the frontend runs separately via `npm run dev`.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "static"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
