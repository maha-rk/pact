"""Compliance Agent: a genuinely separate, independently deployable
service -- the same real "separate FastAPI process" pattern already
proven by the external vendor agents (`vendors/aws_vendor/app.py`),
applied here to one of Pact's own internal agents, closing the
architecture review's "single-process orchestration" gap for the agent
most central to the compliance-rejection feedback loop.

Wraps the exact same deterministic rule evaluation as
`pact/agents/compliance_agent.py` -- no logic duplicated, only the
transport changes (real HTTP call vs. direct function call). Only reached
when `PACT_DISTRIBUTED=true` (see `pact/runtime_factories.py` and
`pact/worker/negotiation_worker.py`); off by default.

Note: unlike the external vendor services, this is an *internal* Pact
agent, not a vendor -- it has no `VendorId` of its own, so its identity
endpoint returns a plain capability declaration rather than the
vendor-scoped `AgentCard` schema, to avoid misrepresenting it as a
vendor identity."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from pact.agents import compliance_agent
from pact.models.schemas import ComplianceResult, Offer, PolicyConstraints

app = FastAPI(title="Pact Compliance Agent Service")

SERVICE_IDENTITY = {
    "name": "Pact Compliance Agent Service (internal)",
    "endpoint": "http://localhost:9101",
    "capabilities": ["check-compliance"],
}


class ComplianceCheckRequest(BaseModel):
    offer: Offer
    policy: PolicyConstraints
    vendor_certifications: list[str] = []


@app.get("/.well-known/agent.json")
def agent_card() -> dict:
    return SERVICE_IDENTITY


@app.post("/check-compliance")
def check_compliance(req: ComplianceCheckRequest) -> ComplianceResult:
    return compliance_agent.check_compliance(req.offer, req.policy, vendor_certifications=req.vendor_certifications)
