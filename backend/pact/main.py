"""Pact core API entrypoint."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # picks up backend/.env (gitignored) -- GEMINI_API_KEY, etc.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pact.api.routes_negotiation import router as negotiation_router

app = FastAPI(title="Pact — Autonomous B2B Procurement Negotiation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(negotiation_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
