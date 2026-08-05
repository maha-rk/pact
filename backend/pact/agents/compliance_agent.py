"""Compliance Agent: checks a candidate deal against explicit policy
constraints as a hard gate (PRD FR-6). Pure deterministic rule evaluation
-- no LLM. Can reject the lowest-price offer on the table; that rejection
is the system's second demo-critical "wow" moment."""

from __future__ import annotations

from pact.models.schemas import ComplianceResult, Offer, PolicyConstraints


def check_compliance(offer: Offer, policy: PolicyConstraints) -> ComplianceResult:
    if offer.vendor_id in policy.blocked_vendors:
        return ComplianceResult(
            vendor_id=offer.vendor_id,
            constraint_name="blocked_vendors",
            passed=False,
            detail=f"{offer.vendor_id.value} is on the blocked-vendor policy list",
        )
    if offer.price_usd > policy.budget_ceiling_usd:
        return ComplianceResult(
            vendor_id=offer.vendor_id,
            constraint_name="budget_ceiling",
            passed=False,
            detail=(
                f"${offer.price_usd:,.2f} exceeds the budget ceiling of "
                f"${policy.budget_ceiling_usd:,.2f}"
            ),
        )
    return ComplianceResult(
        vendor_id=offer.vendor_id,
        constraint_name="all_constraints",
        passed=True,
        detail="Deal satisfies the budget ceiling and vendor block-list constraints",
    )
