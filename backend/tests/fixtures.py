"""Fixture-only vendor/pricing data for internal validation (pytest and
the `--fixture` CLI flag). NEVER shown to a user or judge as a real
result -- this exists purely to prove the deterministic pipeline mechanics
fast, without live network calls, using numbers PULLED FROM the real AWS
Price List Bulk API and the real, live Azure Retail Prices API (not
invented -- see vendors/aws_vendor/pricing_client.py and
vendors/azure_vendor/pricing_client.py, which hit the same live sources
directly for the real integration path).

`FixturePricingSource` itself lives in
`pact/testing_support/fixture_pricing.py` (not here) so a separate
process -- the distributed worker or a standalone agent service -- can
construct one via `pact.runtime_factories.pricing_source()` under
`PACT_FIXTURE_MODE=true` without importing test-only code across a
process boundary. Re-exported here unchanged for existing test imports.
"""

from __future__ import annotations

from pact.models.schemas import PolicyConstraints, Requirement, VendorId
from pact.testing_support.fixture_pricing import FixturePricingSource

__all__ = [
    "FixturePricingSource",
    "FLAGSHIP_CLAIMED_DISCOUNTS",
    "flagship_requirement",
    "flagship_policy",
]


# AWS deliberately claims a committed-use discount that cannot legitimately
# exist for a 3-month term (build plan §5 item 7 -- a scripted, disclosed
# negotiating stance). Azure claims its real, live spot-based discount
# truthfully. GCP is a truthful placeholder pending real API integration.
FLAGSHIP_CLAIMED_DISCOUNTS: dict[VendorId, float] = {
    VendorId.AWS: 0.25,     # claims 25%; real is 0% (no such tier exists) -> wow moment #1
    VendorId.AZURE: 0.8152,  # claims exactly its real, verified spot-based rate
    VendorId.GCP: 0.0,      # claims truthfully; never competitive
}


def flagship_requirement() -> Requirement:
    return Requirement(
        gpu_type="H100",
        gpu_count=8,
        contract_months=3,
        budget_ceiling_usd=115000.0,
        region="us-east-1",
        raw_input="Need 8 H100 GPUs, 3-month contract, $115,000 budget",
    )


def flagship_policy() -> PolicyConstraints:
    return PolicyConstraints(budget_ceiling_usd=115000.0)
