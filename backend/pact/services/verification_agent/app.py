"""Verification Agent: a genuinely separate, independently deployable
service -- the same real "separate FastAPI process" pattern already
proven by the external vendor agents and the standalone Compliance
Agent service, applied here to close the architecture review's
"Verification Agent process isolation is deferred in the distributed
execution path" gap.

Wraps the exact same deterministic verify_claim logic as
`pact/agents/verification_agent.py` -- no logic duplicated, only the
transport changes (real HTTP call vs. direct function call). Resolves
its own `pricing_source()` and `plausibility_screener()` locally via
`pact/runtime_factories.py` (the same env-driven, probe-then-trust
factories the worker and the API use), since neither a `PricingSource`
object nor a screener callable can cross a real process boundary.

Only reached when `PACT_DISTRIBUTED=true`; off by default."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from pact import runtime_factories
from pact.agents import verification_agent
from pact.models.schemas import Offer, Requirement, VerificationResult

app = FastAPI(title="Pact Verification Agent Service")

SERVICE_IDENTITY = {
    "name": "Pact Verification Agent Service (internal)",
    "endpoint": "http://localhost:9102",
    "capabilities": ["verify"],
}


class VerificationCheckRequest(BaseModel):
    offer: Offer
    requirement: Requirement


@app.get("/.well-known/agent.json")
def agent_card() -> dict:
    return SERVICE_IDENTITY


@app.post("/verify")
def verify(req: VerificationCheckRequest) -> VerificationResult:
    return verification_agent.verify(
        req.offer,
        req.requirement,
        pricing_source=runtime_factories.pricing_source(),
        plausibility_screener=runtime_factories.plausibility_screener(),
    )
