"""The pact-core API: what the frontend and the demo actually talk to.
Both required UI surfaces (PRD §22, FR-10) read GET /negotiations/{id}
and render two projections of the same record."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pact.a2a.vendor_client import HttpVendorClient
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


@router.post("", response_model=NegotiationState)
def create_negotiation(req: NegotiationRequest) -> NegotiationState:
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
    )
    _STORE[state.negotiation_id] = state
    return state


@router.get("/{negotiation_id}", response_model=NegotiationState)
def get_negotiation(negotiation_id: str) -> NegotiationState:
    state = _STORE.get(negotiation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return state


@router.post("/{negotiation_id}/approve", response_model=NegotiationState)
def approve_negotiation(negotiation_id: str, req: ApprovalRequest) -> NegotiationState:
    state = _STORE.get(negotiation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if state.status != NegotiationStatus.AGREED_PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Cannot approve a negotiation in status {state.status.value}")
    approval.approve(state, approved_by=req.approved_by)
    return state


@router.get("", response_model=list[NegotiationState])
def list_negotiations() -> list[NegotiationState]:
    return list(_STORE.values())
