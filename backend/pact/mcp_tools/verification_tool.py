"""MCP tool: verify_claim. Used by the Verification Agent (PRD §17, FR-5)."""

from __future__ import annotations

from pact.mcp_tools.pricing_tool import PricingSource
from pact.models.schemas import Offer, Requirement, VerificationResult

MATCH_TOLERANCE = 0.005
"""A claimed rate within 0.5 percentage points of the real rate is treated
as matching (floating point / rounding slack), not as a mismatch."""


def verify_claim(offer: Offer, requirement: Requirement, pricing_source: PricingSource) -> VerificationResult:
    """Cross-check a vendor's claimed committed-use discount rate against
    real, independently-sourced pricing data. A claim MORE favorable than
    what the real data supports is a mismatch (PRD §18's flagship scenario);
    a claim equal to or less favorable than real always matches."""
    real_rate = pricing_source.real_committed_use_discount_rate(offer.vendor_id, requirement)
    claimed = offer.claimed_discount_rate or 0.0
    matched = claimed <= real_rate + MATCH_TOLERANCE
    return VerificationResult(
        vendor_id=offer.vendor_id,
        claim_checked=f"committed-use discount rate for a {requirement.contract_months}-month term",
        claimed_value=claimed,
        actual_value=real_rate,
        source=pricing_source.source_label(offer.vendor_id),
        matched=matched,
    )
