"""AWS Vendor Agent: a genuinely separate, independently deployed
A2A-addressable service (PRD §17). Wraps real AWS pricing data. Operated
by the Pact team -- not by Amazon (see PRD §32's explicit non-claim)."""

from __future__ import annotations

from fastapi import FastAPI

from pact.agents.negotiation_agent import vendor_offer_at_round
from pact.models.schemas import AgentCard, Offer, VendorId
from vendors.aws_vendor.pricing_client import AWSPricingClient

app = FastAPI(title="Pact AWS Vendor Agent")
pricing_client = AWSPricingClient()

AGENT_CARD = AgentCard(
    vendor_id=VendorId.AWS,
    name="AWS Vendor Agent (Pact-operated)",
    endpoint="http://localhost:9001",
    capabilities=["negotiate", "quote"],
)


@app.get("/.well-known/agent.json")
def agent_card() -> AgentCard:
    return AGENT_CARD


@app.post("/negotiate")
def negotiate(
    gpu_count: int,
    contract_months: int,
    round_number: int,
    max_rounds: int,
    claimed_discount_rate: float,
) -> Offer:
    """Returns this vendor's counter-offer for one negotiation round.
    `claimed_discount_rate` is supplied by the caller (the Negotiation
    Agent) reflecting this vendor's current negotiating stance -- initial
    claim on round 1, corrected rate after any verification challenge.
    """
    from pact.models.schemas import Requirement

    requirement = Requirement(
        gpu_type="H100",
        gpu_count=gpu_count,
        contract_months=contract_months,
        budget_ceiling_usd=0,  # not needed for pricing lookup
        raw_input="",
    )
    list_price = pricing_client.list_price(VendorId.AWS, requirement)
    return vendor_offer_at_round(
        vendor_id=VendorId.AWS,
        list_price=list_price,
        claimed_discount_rate=claimed_discount_rate,
        round_number=round_number,
        max_rounds=max_rounds,
    )


@app.get("/real-pricing")
def real_pricing(contract_months: int = 3) -> dict:
    """Debug/demo endpoint: what does AWS's real pricing data actually say
    for this contract length? Used to show a judge the live source behind
    a verification result."""
    from pact.models.schemas import Requirement

    requirement = Requirement(
        gpu_type="H100", gpu_count=8, contract_months=contract_months, budget_ceiling_usd=0, raw_input=""
    )
    return {
        "list_price_usd": pricing_client.list_price(VendorId.AWS, requirement),
        "real_committed_use_discount_rate": pricing_client.real_committed_use_discount_rate(
            VendorId.AWS, requirement
        ),
        "source": pricing_client.source_label(VendorId.AWS),
    }
