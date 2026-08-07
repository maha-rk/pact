"""Compliance Agent: checks a candidate deal against explicit policy
constraints as a hard gate (PRD FR-6). Pure deterministic rule evaluation
-- no LLM. Can reject the lowest-price offer on the table; that rejection
is the system's second demo-critical "wow" moment."""

from __future__ import annotations

from pact.models.schemas import ComplianceResult, Offer, PolicyConstraints


def check_compliance(
    offer: Offer,
    policy: PolicyConstraints,
    vendor_certifications: list[str] | None = None,
    vendor_renewable_energy_pct: float | None = None,
) -> ComplianceResult:
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
    if policy.required_certifications:
        held = set(vendor_certifications or [])
        missing = [c for c in policy.required_certifications if c not in held]
        if missing:
            return ComplianceResult(
                vendor_id=offer.vendor_id,
                constraint_name="required_certifications",
                passed=False,
                detail=f"{offer.vendor_id.value} is missing required certification(s): {', '.join(missing)}",
            )
    if policy.min_renewable_energy_pct is not None:
        declared = vendor_renewable_energy_pct
        if declared is None or declared < policy.min_renewable_energy_pct:
            declared_label = "an undisclosed" if declared is None else f"a declared {declared:.1f}%"
            return ComplianceResult(
                vendor_id=offer.vendor_id,
                constraint_name="esg_renewable_energy",
                passed=False,
                detail=(
                    f"{offer.vendor_id.value} has {declared_label} renewable-energy match, "
                    f"below the required {policy.min_renewable_energy_pct:.1f}% ESG threshold"
                ),
            )
    return ComplianceResult(
        vendor_id=offer.vendor_id,
        constraint_name="all_constraints",
        passed=True,
        detail="Deal satisfies the budget ceiling, vendor block-list, certification, and ESG constraints",
    )
