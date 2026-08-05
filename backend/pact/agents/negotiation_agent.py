"""Negotiation Agent: deterministic offer generation for both sides of a
negotiation round (PRD FR-3, FR-4, §16). No LLM ever determines a price."""

from __future__ import annotations

from pact.models.schemas import Offer, VendorId
from pact.negotiation.concession import ConcessionParams, offer_at_round

NEGOTIATION_STRETCH_FACTOR = 1.05
"""The Negotiation Agent's own walk-away point is deliberately looser than
the hard Compliance-enforced budget ceiling (PRD §19's Compliance gate) --
this is what allows a deal to clear negotiation on price yet still be
rejected by Compliance, matching the Flagship Demonstration Scenario
exactly. It's a disclosed negotiating buffer, not a policy override."""


def buyer_offer_at_round(
    opening_bid: float, budget_ceiling: float, round_number: int, max_rounds: int
) -> float:
    """The buyer's own deterministic offer sequence: starts low, concedes
    upward toward a stretch reservation above budget (FR-4)."""
    stretch_reservation = budget_ceiling * NEGOTIATION_STRETCH_FACTOR
    params = ConcessionParams(opening=opening_bid, reservation=stretch_reservation, total_rounds=max_rounds)
    return offer_at_round(params, round_number)


def vendor_offer_at_round(
    vendor_id: VendorId,
    list_price: float,
    claimed_discount_rate: float,
    round_number: int,
    max_rounds: int,
) -> Offer:
    """A vendor's deterministic counter-offer sequence: starts at its full
    list price, concedes toward a reservation implied by whatever discount
    rate it is CURRENTLY claiming. If that claim gets corrected after a
    failed verification, subsequent rounds use the corrected rate."""
    reservation = list_price * (1 - claimed_discount_rate)
    params = ConcessionParams(opening=list_price, reservation=reservation, total_rounds=max_rounds)
    price = offer_at_round(params, round_number)
    return Offer(
        vendor_id=vendor_id,
        round_number=round_number,
        price_usd=round(price, 2),
        claimed_discount_rate=claimed_discount_rate,
    )
