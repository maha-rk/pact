"""MCP tool: verify_claim. Used by the Verification Agent (PRD §17, FR-5)."""

from __future__ import annotations

from typing import Callable

from pact.mcp_tools.pricing_tool import PricingSource
from pact.models.schemas import Offer, Requirement, VerificationResult

MATCH_TOLERANCE = 0.005
"""A claimed rate within 0.5 percentage points of the real rate is treated
as matching (floating point / rounding slack), not as a mismatch."""

PlausibilityScreener = Callable[[str, float, int], str]


def verify_claim(
    offer: Offer,
    requirement: Requirement,
    pricing_source: PricingSource,
    plausibility_screener: PlausibilityScreener | None = None,
) -> VerificationResult:
    """Cross-check a vendor's claimed committed-use discount rate against
    real, independently-sourced pricing data. A claim MORE favorable than
    what the real data supports is a mismatch (PRD §18's flagship scenario);
    a claim equal to or less favorable than real always matches.

    If `plausibility_screener` (Gemma) is supplied, it runs first as a
    fast, independent, best-effort signal -- its result is attached to the
    output but never influences `matched`, which stays a deterministic
    numeric comparison (PRD §16)."""
    plausibility_screen = None
    if plausibility_screener is not None:
        try:
            plausibility_screen = plausibility_screener(
                offer.vendor_id.value, offer.claimed_discount_rate or 0.0, requirement.contract_months
            )
        except Exception:
            pass  # best-effort only; never blocks or affects the verdict (PRD §27)

    real_rate = pricing_source.real_committed_use_discount_rate(offer.vendor_id, requirement)
    claimed = offer.claimed_discount_rate or 0.0
    matched = claimed <= real_rate + MATCH_TOLERANCE
    return VerificationResult(
        vendor_id=offer.vendor_id,
        claim_checked=f"discount rate claimed for a {requirement.contract_months}-month term",
        claimed_value=claimed,
        actual_value=real_rate,
        source=pricing_source.source_label(offer.vendor_id),
        matched=matched,
        plausibility_screen=plausibility_screen,
    )
