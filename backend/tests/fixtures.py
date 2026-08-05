"""Fixture-only vendor/pricing data for internal validation (pytest and
the `--fixture` CLI flag). NEVER shown to a user or judge as a real
result -- this exists purely to prove the deterministic pipeline mechanics
before real vendor integrations exist (build plan Day 1 exit criteria).

Numbers are calibrated so the Flagship Demonstration Scenario's exact
narrative plays out: AWS's inflated claim is caught in round 1 and,
even after correction to its real (still-too-high) rate, AWS cannot clear
the strict budget ceiling -- while Azure, which claims truthfully
throughout, converges on a compliant deal by the final round.
"""

from __future__ import annotations

from pact.models.schemas import PolicyConstraints, Requirement, VendorId
from pact.mcp_tools.pricing_tool import PricingSource


class FixturePricingSource:
    """Mirrors the shape real AWS/Azure/GCP pricing lookups will have."""

    _DATA = {
        VendorId.AWS: {
            "list_price": 12000.0,
            "real_max_discount_rate": 0.15,  # real floor: $10,200 -- always exceeds the $10k budget
            "source": "AWS Price List Bulk API (fixture)",
        },
        VendorId.AZURE: {
            "list_price": 11500.0,
            "real_max_discount_rate": 0.15,  # real floor: $9,775 -- clears the $10k budget
            "source": "Azure Retail Prices API (fixture)",
        },
        VendorId.GCP: {
            "list_price": 11800.0,
            "real_max_discount_rate": 0.10,  # real floor: $10,620 -- always exceeds the $10k budget
            "source": "GCP Cloud Billing Catalog API (fixture)",
        },
    }

    def list_price(self, vendor_id: VendorId, requirement: Requirement) -> float:
        return self._DATA[vendor_id]["list_price"]

    def real_committed_use_discount_rate(self, vendor_id: VendorId, requirement: Requirement) -> float:
        return self._DATA[vendor_id]["real_max_discount_rate"]

    def source_label(self, vendor_id: VendorId) -> str:
        return self._DATA[vendor_id]["source"]


# AWS deliberately claims a more-favorable discount than its real tiers
# support -- a scripted, disclosed negotiating stance (build plan §5 item
# 7). What must never be fabricated is the verification check itself,
# which always compares against FixturePricingSource's real rate above.
FLAGSHIP_CLAIMED_DISCOUNTS: dict[VendorId, float] = {
    VendorId.AWS: 0.25,    # claims 25%; real is 15% -> mismatch, wow moment #1
    VendorId.AZURE: 0.15,  # claims exactly its real rate -> always verified true
    VendorId.GCP: 0.10,    # claims exactly its real rate -> always verified true
}


def flagship_requirement() -> Requirement:
    return Requirement(
        gpu_type="H100",
        gpu_count=8,
        contract_months=3,
        budget_ceiling_usd=10000.0,
        region="us-east-1",
        raw_input="Need 8 H100 GPUs, 3-month contract, $10,000 budget",
    )


def flagship_policy() -> PolicyConstraints:
    return PolicyConstraints(budget_ceiling_usd=10000.0)
