"""The pact-core API: what the frontend and the demo actually talk to.
Both required UI surfaces (PRD §22, FR-10) read GET /negotiations/{id}
and render two projections of the same record."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

import os

from pact.a2a.vendor_client import HttpVendorClient
from pact.api.gateway import limiter, require_bearer_token
from pact.logging import bigquery_sink
from pact.models.schemas import AgentCard, PolicyConstraints, Requirement, VendorId
from pact.orchestration import approval
from pact.orchestration.graph import run_negotiation
from pact.orchestration.state import NegotiationState, NegotiationStatus

router = APIRouter(prefix="/negotiations", tags=["negotiations"])

# In-memory store for this build; swapped for BigQuery-backed persistence
# once negotiation logging (FR-9) lands -- see pact/logging/.
_STORE: dict[str, NegotiationState] = {}

VENDOR_ENDPOINTS = {
    VendorId.AWS: "http://localhost:9001",
    VendorId.AZURE: "http://localhost:9002",
}
AGENT_CARDS = {
    vid: AgentCard(vendor_id=vid, name=f"{vid.value.upper()} Vendor Agent", endpoint=ep, capabilities=["negotiate"])
    for vid, ep in VENDOR_ENDPOINTS.items()
}


class NegotiationRequest(BaseModel):
    gpu_type: str = "H100"
    gpu_count: int
    contract_months: int
    budget_ceiling_usd: float
    region: str | None = None
    raw_input: str
    blocked_vendors: list[VendorId] = []
    required_certifications: list[str] = []
    initial_claimed_discounts: dict[VendorId, float]


class ApprovalRequest(BaseModel):
    approved_by: str


def _pricing_source():
    # Imported lazily so importing this router doesn't require the vendor
    # packages to be on the path in every deployment context.
    from vendors.aws_vendor.pricing_client import AWSPricingClient
    from vendors.azure_vendor.pricing_client import AzurePricingClient

    aws, azure = AWSPricingClient(), AzurePricingClient()

    class _Combined:
        def list_price(self, vendor_id, requirement):
            return (aws if vendor_id == VendorId.AWS else azure).list_price(vendor_id, requirement)

        def real_committed_use_discount_rate(self, vendor_id, requirement):
            client = aws if vendor_id == VendorId.AWS else azure
            return client.real_committed_use_discount_rate(vendor_id, requirement)

        def source_label(self, vendor_id):
            return (aws if vendor_id == VendorId.AWS else azure).source_label(vendor_id)

    return _Combined()


def _narrator():
    """Real Gemini narration if a key is configured; None otherwise --
    the deterministic template fallback in decision_agent handles that
    case gracefully (PRD §27)."""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from pact.models.gemini_client import narrate_reasoning

    return narrate_reasoning


def _plausibility_screener():
    """Real Gemma pre-screen if the local Ollama instance is reachable;
    None otherwise -- verification's deterministic verdict never depends
    on this (PRD §27)."""
    import httpx

    try:
        httpx.get("http://localhost:11434/api/tags", timeout=1.0).raise_for_status()
    except Exception:
        return None
    from pact.models.gemma_client import plausibility_screen

    return plausibility_screen


@router.post("", response_model=NegotiationState, dependencies=[Depends(require_bearer_token)])
@limiter.limit("20/minute")
def create_negotiation(request: Request, req: NegotiationRequest, background_tasks: BackgroundTasks) -> NegotiationState:
    requirement = Requirement(
        gpu_type=req.gpu_type,
        gpu_count=req.gpu_count,
        contract_months=req.contract_months,
        budget_ceiling_usd=req.budget_ceiling_usd,
        region=req.region,
        raw_input=req.raw_input,
    )
    policy = PolicyConstraints(
        budget_ceiling_usd=req.budget_ceiling_usd,
        blocked_vendors=req.blocked_vendors,
        required_certifications=req.required_certifications,
    )
    candidate_vendors = list(req.initial_claimed_discounts.keys())

    state = run_negotiation(
        requirement=requirement,
        policy=policy,
        candidate_vendors=candidate_vendors,
        agent_cards={v: AGENT_CARDS[v] for v in candidate_vendors},
        pricing_source=_pricing_source(),
        initial_claimed_discounts=req.initial_claimed_discounts,
        vendor_client=HttpVendorClient(VENDOR_ENDPOINTS),
        narrator=_narrator(),
        plausibility_screener=_plausibility_screener(),
    )
    _STORE[state.negotiation_id] = state
    # BigQuery load jobs take real seconds -- never hold the API response on
    # them (PRD §27's discipline applied to latency, not just correctness).
    background_tasks.add_task(bigquery_sink.write_negotiation, state)
    return state


@router.get("/{negotiation_id}", response_model=NegotiationState)
def get_negotiation(negotiation_id: str) -> NegotiationState:
    state = _STORE.get(negotiation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return state


@router.post("/{negotiation_id}/approve", response_model=NegotiationState, dependencies=[Depends(require_bearer_token)])
@limiter.limit("20/minute")
def approve_negotiation(
    request: Request, negotiation_id: str, req: ApprovalRequest, background_tasks: BackgroundTasks
) -> NegotiationState:
    state = _STORE.get(negotiation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if state.status != NegotiationStatus.AGREED_PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Cannot approve a negotiation in status {state.status.value}")
    approval.approve(state, approved_by=req.approved_by)
    background_tasks.add_task(bigquery_sink.write_negotiation, state)  # re-sync: records the approval too
    return state


@router.get("", response_model=list[NegotiationState])
def list_negotiations() -> list[NegotiationState]:
    return list(_STORE.values())
