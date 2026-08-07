"""Azure Vendor Agent: a genuinely separate, independently deployed
A2A-addressable service (PRD §17). Wraps real, live Azure pricing data.
Operated by the Pact team -- not by Microsoft (see PRD §32's explicit
non-claim)."""

from __future__ import annotations

from fastapi import FastAPI

from pact.agents.negotiation_agent import vendor_offer_at_round
from pact.models.schemas import AgentCard, Offer, Requirement, VendorId
from vendors.azure_vendor.pricing_client import AzurePricingClient

app = FastAPI(title="Pact Azure Vendor Agent")
pricing_client = AzurePricingClient()

AGENT_CARD = AgentCard(
    vendor_id=VendorId.AZURE,
    name="Azure Vendor Agent (Pact-operated)",
    endpoint="http://localhost:9002",
    capabilities=["negotiate", "quote"],
    # Self-declared in the Agent Card, matching real-world Azure compliance
    # documentation -- unlike pricing claims, certifications aren't
    # independently re-verified against a live API in this build's scope.
    certifications=["SOC2", "ISO27001"],
    # Microsoft matched 100% of its annual global electricity consumption
    # with renewable energy (2025 Environmental Sustainability Report) --
    # https://blogs.microsoft.com/on-the-issues/2025/05/29/environmental-sustainability-report/.
    # Same disclosure scope as certifications: a real, published company-
    # wide figure, not independently re-verified per-region here.
    renewable_energy_pct=100.0,
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
    requirement = Requirement(
        gpu_type="H100", gpu_count=gpu_count, contract_months=contract_months, budget_ceiling_usd=0, raw_input=""
    )
    list_price = pricing_client.list_price(VendorId.AZURE, requirement)
    return vendor_offer_at_round(
        vendor_id=VendorId.AZURE,
        list_price=list_price,
        claimed_discount_rate=claimed_discount_rate,
        round_number=round_number,
        max_rounds=max_rounds,
    )


@app.get("/real-pricing")
def real_pricing(contract_months: int = 3) -> dict:
    requirement = Requirement(
        gpu_type="H100", gpu_count=8, contract_months=contract_months, budget_ceiling_usd=0, raw_input=""
    )
    return {
        "list_price_usd": pricing_client.list_price(VendorId.AZURE, requirement),
        "real_discount_rate": pricing_client.real_committed_use_discount_rate(VendorId.AZURE, requirement),
        "source": pricing_client.source_label(VendorId.AZURE),
    }
