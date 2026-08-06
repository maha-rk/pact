"""Decision Agent: produces the final Decision/Evidence/Reasoning output
(PRD FR-7). Never a bare confidence score -- every evidence item traces to
a real source already established earlier in the pipeline."""

from __future__ import annotations

from typing import Callable

from pact.models.schemas import (
    ComplianceResult,
    Decision,
    EvidenceItem,
    Offer,
    VerificationResult,
)

Narrator = Callable[..., str]


def build_decision(
    negotiation_id: str,
    winning_offer: Offer | None,
    verification: VerificationResult | None,
    compliance: ComplianceResult | None,
    narrator: Narrator | None = None,
) -> tuple[Decision, str | None]:
    """Returns (Decision, narrator_error). narrator_error is None if no
    narrator was supplied or it succeeded; otherwise it's the failure
    reason, for the caller to log (PRD §27 -- disclosed, not masked)."""
    if winning_offer is None:
        decision = Decision(
            negotiation_id=negotiation_id,
            selected_vendor=None,
            final_price_usd=None,
            evidence=[],
            reasoning=(
                "No vendor produced an offer that passed both the verification and "
                "compliance gates within the negotiation round limit. No compliant "
                "deal was found."
            ),
        )
        return decision, None

    evidence: list[EvidenceItem] = []
    if verification is not None:
        evidence.append(
            EvidenceItem(
                label="Verified pricing claim",
                value=f"{verification.actual_value:.1%} discount confirmed against real pricing data",
                source=verification.source,
            )
        )
    if compliance is not None:
        evidence.append(
            EvidenceItem(
                label="Compliance check",
                value=compliance.detail,
                source="Compliance Agent policy evaluation",
            )
        )
    evidence.append(
        EvidenceItem(
            label="Final negotiated price",
            value=f"${winning_offer.price_usd:,.2f}",
            source=f"Negotiation round {winning_offer.round_number} with {winning_offer.vendor_id.value}",
        )
    )

    # Deterministic fallback reasoning -- always computed first, so a
    # narrator failure never blocks producing a decision (PRD §27).
    reasoning = (
        f"{winning_offer.vendor_id.value.upper()} was selected because its final offer of "
        f"${winning_offer.price_usd:,.2f} passed independent verification against real pricing "
        f"data and satisfied every active policy constraint."
    )
    narrator_error: str | None = None
    if narrator is not None:
        try:
            reasoning = narrator(
                winning_offer.vendor_id.value.upper(),
                winning_offer.price_usd,
                [f"{e.label}: {e.value} (source: {e.source})" for e in evidence],
                negotiation_id=negotiation_id,
            )
        except Exception as exc:
            narrator_error = str(exc)  # keep the deterministic fallback; never block on a narration failure

    decision = Decision(
        negotiation_id=negotiation_id,
        selected_vendor=winning_offer.vendor_id,
        final_price_usd=winning_offer.price_usd,
        evidence=evidence,
        reasoning=reasoning,
    )
    return decision, narrator_error
