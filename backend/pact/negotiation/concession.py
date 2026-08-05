"""Deterministic concession-curve negotiation logic.

Every offer value produced by Pact traces to this module's pure functions.
No language model participates in this path (PRD FR-4, §16): given identical
inputs, negotiation MUST produce an identical offer sequence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConcessionParams:
    """Parameters governing one party's concession curve for a negotiation.

    opening: the first offer made (most favorable to this party).
    reservation: the walk-away point (BATNA-derived); never crossed.
    total_rounds: the round at which the curve reaches `reservation`.
    beta: concession-curve shape. beta=1 is linear; beta>1 concedes slowly
        at first then quickly near the deadline (time-decay "Boulware"
        style); beta<1 concedes quickly at first then slowly.
    """

    opening: float
    reservation: float
    total_rounds: int
    beta: float = 2.0

    def __post_init__(self) -> None:
        if self.total_rounds < 1:
            raise ValueError("total_rounds must be >= 1")
        if self.beta <= 0:
            raise ValueError("beta must be > 0")


def offer_at_round(params: ConcessionParams, round_number: int) -> float:
    """Return the deterministic offer value for a given round.

    round_number is 1-indexed. round 1 == opening. round >= total_rounds
    clamps to reservation (never conceding past the walk-away point).
    """
    if round_number < 1:
        raise ValueError("round_number must be >= 1")

    if round_number >= params.total_rounds:
        return params.reservation

    t = (round_number - 1) / (params.total_rounds - 1) if params.total_rounds > 1 else 1.0
    fraction_conceded = t**params.beta
    span = params.opening - params.reservation
    return params.opening - span * fraction_conceded


def generate_offer_sequence(params: ConcessionParams) -> list[float]:
    """Return the full, deterministic offer sequence for these params.

    Reproducibility (PRD NFR "Reproducibility"): calling this twice with
    identical params always returns an identical list.
    """
    return [offer_at_round(params, r) for r in range(1, params.total_rounds + 1)]


def reservation_price_for_buyer(budget_ceiling: float, market_floor: float) -> float:
    """A buyer's reservation price is the lower of its stated budget ceiling
    and the best price a real market data source indicates is achievable —
    never a value invented independent of those two real inputs.
    """
    return min(budget_ceiling, market_floor)
