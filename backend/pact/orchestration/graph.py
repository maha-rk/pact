"""The 6-agent pipeline: Buyer -> Discovery -> Negotiation -> then, in
order, the Verification gate -> Compliance gate -> Comparison (PRD §19),
with two feedback loops back to Negotiation (verification-mismatch and
compliance-violation). This is the authoritative gate order -- it matches
§19 and the ARCHITECTURE.md §3 sequence diagram, not the inconsistent box
order in ARCHITECTURE.md §2 (see the build plan for why)."""

from __future__ import annotations

import uuid

from pact.a2a.compliance_client import HttpComplianceClient
from pact.a2a.vendor_client import HttpVendorClient, VendorUnavailableError
from pact.agents import compliance_agent, decision_agent, discovery_agent, verification_agent
from pact.agents.negotiation_agent import buyer_offer_at_round, vendor_offer_at_round
from pact.mcp_tools.pricing_tool import PricingSource
from pact.mcp_tools.verification_tool import PlausibilityScreener
from pact.models.schemas import AgentCard, Offer, PolicyConstraints, Requirement, VendorId
from pact.orchestration.state import EventType, NegotiationState, NegotiationStatus

DEFAULT_MAX_ROUNDS = 6
DEFAULT_BUYER_OPENING_FRACTION = 0.5
"""The buyer's opening bid as a fraction of its own budget ceiling -- an
aggressive first offer, per standard concession-curve practice. Based on
the buyer's budget rather than vendor list prices, since real vendor list
prices can vary enormously (on-demand vs. real short-term-available
discount mechanisms like spot pricing) and shouldn't anchor the buyer's
own opening posture."""


def run_discovery_phase(
    state: NegotiationState,
    candidate_vendors: list[VendorId],
    agent_cards: dict[VendorId, AgentCard],
) -> None:
    """Discovery Agent: verify vendor identity before negotiating (FR-2).
    Mutates `state.active_vendors` / `state.unavailable_vendors` in place
    and, if no vendor passes, sets a terminal NO_COMPLIANT_DEAL decision --
    same phase boundary the ADK orchestration layer (`pact/adk/pipeline.py`)
    composes as its own real ADK agent."""
    for vendor_id in candidate_vendors:
        card = agent_cards[vendor_id]
        if discovery_agent.verify_agent_card(card):
            state.active_vendors.append(vendor_id)
            state.log(
                EventType.VENDOR_DISCOVERED,
                vendor_id=vendor_id,
                detail=f"Agent Card verified: {card.name} ({card.endpoint})",
            )
        else:
            state.unavailable_vendors.append(vendor_id)
            state.log(
                EventType.VENDOR_UNAVAILABLE,
                vendor_id=vendor_id,
                detail="Agent Card missing required fields or unreachable",
            )

    if not state.active_vendors:
        state.status = NegotiationStatus.NO_COMPLIANT_DEAL
        state.log(EventType.NO_COMPLIANT_DEAL, detail="No vendors passed identity verification")
        state.decision, _ = decision_agent.build_decision(state.negotiation_id, None, None, None)


def run_negotiation_and_decision_phase(
    state: NegotiationState,
    requirement: Requirement,
    policy: PolicyConstraints,
    agent_cards: dict[VendorId, AgentCard],
    pricing_source: PricingSource,
    initial_claimed_discounts: dict[VendorId, float],
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    vendor_client: HttpVendorClient | None = None,
    narrator: decision_agent.Narrator | None = None,
    plausibility_screener: PlausibilityScreener | None = None,
    compliance_client: HttpComplianceClient | None = None,
) -> None:
    """Negotiation Agent rounds -> Verification gate -> Compliance gate ->
    Comparison -> Decision Agent (PRD §19). Requires `state.active_vendors`
    already populated by `run_discovery_phase`. Mutates `state` in place.

    If `compliance_client` is provided, each round's compliance check is
    made over real HTTP against the standalone Compliance Agent service
    (`pact/services/compliance_agent/app.py`) -- the same "real transport,
    identical math" pattern `vendor_client` already uses for vendor
    offers. Without it (the default), compliance is checked in-process via
    a direct function call, exactly as today."""
    list_prices = {v: pricing_source.list_price(v, requirement) for v in state.active_vendors}
    current_claimed_discount = dict(initial_claimed_discounts)
    buyer_opening = requirement.budget_ceiling_usd * DEFAULT_BUYER_OPENING_FRACTION

    winning_offer: Offer | None = None
    winning_verification = None
    winning_compliance = None

    for round_number in range(1, max_rounds + 1):
        buyer_price = buyer_offer_at_round(buyer_opening, requirement.budget_ceiling_usd, round_number, max_rounds)
        round_price_acceptable: list[tuple[Offer, object]] = []  # (offer, verification)

        # --- Negotiation Agent: simultaneous offers to every active vendor (FR-3) ---
        for vendor_id in list(state.active_vendors):
            if vendor_client is not None:
                try:
                    offer = vendor_client.negotiate(
                        vendor_id=vendor_id,
                        gpu_count=requirement.gpu_count,
                        contract_months=requirement.contract_months,
                        round_number=round_number,
                        max_rounds=max_rounds,
                        claimed_discount_rate=current_claimed_discount[vendor_id],
                    )
                except VendorUnavailableError as exc:
                    # PRD §27: disclose, never substitute an invented price.
                    state.active_vendors.remove(vendor_id)
                    state.unavailable_vendors.append(vendor_id)
                    state.log(EventType.VENDOR_UNAVAILABLE, vendor_id=vendor_id, detail=str(exc))
                    continue
            else:
                offer = vendor_offer_at_round(
                    vendor_id=vendor_id,
                    list_price=list_prices[vendor_id],
                    claimed_discount_rate=current_claimed_discount[vendor_id],
                    round_number=round_number,
                    max_rounds=max_rounds,
                )
            state.offers.append(offer)
            state.log(
                EventType.OFFER_MADE,
                vendor_id=vendor_id,
                round_number=round_number,
                detail=f"${offer.price_usd:,.2f} (claims {offer.claimed_discount_rate:.0%} discount)",
            )

            # --- Verification gate: every claim checked, every round (FR-5) ---
            result = verification_agent.verify(
                offer, requirement, pricing_source, plausibility_screener=plausibility_screener
            )
            state.verification_results.append(result)
            if result.plausibility_screen:
                state.log(
                    EventType.PLAUSIBILITY_SCREENED,
                    vendor_id=vendor_id,
                    round_number=round_number,
                    detail=f"Gemma (self-hosted, independent of the deterministic verdict): {result.plausibility_screen}",
                )
            if result.matched:
                state.log(
                    EventType.CLAIM_VERIFIED,
                    vendor_id=vendor_id,
                    round_number=round_number,
                    detail=f"Claimed {result.claimed_value:.0%} matches real rate ({result.source})",
                )
            else:
                state.log(
                    EventType.CLAIM_REJECTED,
                    vendor_id=vendor_id,
                    round_number=round_number,
                    detail=(
                        f"Claimed {result.claimed_value:.0%} does not match real "
                        f"{result.actual_value:.0%} ({result.source})"
                    ),
                )
                state.log(
                    EventType.RENEGOTIATION_TRIGGERED,
                    vendor_id=vendor_id,
                    round_number=round_number,
                    detail="Claim rejected; vendor challenged to renegotiate with a corrected rate",
                )
                # Correction: from the NEXT round on, this vendor claims the real rate.
                current_claimed_discount[vendor_id] = result.actual_value
                continue  # this round's offer does not proceed to compliance/comparison

            if offer.price_usd <= buyer_price:
                round_price_acceptable.append((offer, result))

        # --- Compliance gate: verified, price-acceptable offers only (FR-6) ---
        round_compliant: list[tuple[Offer, object, object]] = []
        for offer, verification in round_price_acceptable:
            vendor_certs = agent_cards[offer.vendor_id].certifications
            if compliance_client is not None:
                compliance = compliance_client.check_compliance(offer, policy, vendor_certifications=vendor_certs)
            else:
                compliance = compliance_agent.check_compliance(offer, policy, vendor_certifications=vendor_certs)
            state.compliance_results.append(compliance)
            if compliance.passed:
                state.log(
                    EventType.COMPLIANCE_PASSED,
                    vendor_id=offer.vendor_id,
                    round_number=round_number,
                    detail=compliance.detail,
                )
                round_compliant.append((offer, verification, compliance))
            else:
                state.log(
                    EventType.COMPLIANCE_REJECTED,
                    vendor_id=offer.vendor_id,
                    round_number=round_number,
                    detail=compliance.detail,
                )
                state.log(
                    EventType.RENEGOTIATION_TRIGGERED,
                    vendor_id=offer.vendor_id,
                    round_number=round_number,
                    detail="Deal rejected on policy grounds; renegotiating with an alternative vendor",
                )

        # --- Comparison: best offer among vendors passing both gates (§19) ---
        if round_compliant:
            winning_offer, winning_verification, winning_compliance = min(
                round_compliant, key=lambda item: item[0].price_usd
            )
            break

    if winning_offer is None:
        state.status = NegotiationStatus.NO_COMPLIANT_DEAL
        state.log(
            EventType.NO_COMPLIANT_DEAL,
            detail="No vendor produced a verified, compliant offer within the round limit",
        )
        state.decision, _ = decision_agent.build_decision(state.negotiation_id, None, None, None)
        return

    state.status = NegotiationStatus.AGREED_PENDING_APPROVAL
    state.decision, narrator_error = decision_agent.build_decision(
        state.negotiation_id, winning_offer, winning_verification, winning_compliance, narrator=narrator
    )
    if narrator_error is not None:
        state.log(
            EventType.NARRATION_DEGRADED,
            vendor_id=winning_offer.vendor_id,
            round_number=winning_offer.round_number,
            detail=f"Gemini narration unavailable ({narrator_error}); used deterministic reasoning template instead",
        )
    state.log(
        EventType.DECISION_PRODUCED,
        vendor_id=winning_offer.vendor_id,
        round_number=winning_offer.round_number,
        detail=state.decision.reasoning,
    )


def run_negotiation(
    requirement: Requirement,
    policy: PolicyConstraints,
    candidate_vendors: list[VendorId],
    agent_cards: dict[VendorId, AgentCard],
    pricing_source: PricingSource,
    initial_claimed_discounts: dict[VendorId, float],
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    vendor_client: HttpVendorClient | None = None,
    narrator: decision_agent.Narrator | None = None,
    plausibility_screener: PlausibilityScreener | None = None,
    compliance_client: HttpComplianceClient | None = None,
    negotiation_id: str | None = None,
) -> NegotiationState:
    """`negotiation_id`: pass an explicit ID when the caller must know it
    before this function returns (the distributed API path mints one,
    publishes it to a worker, then polls for it) -- default `None` mints
    a fresh `uuid.uuid4()` exactly as before, unaffected for every
    existing caller/test.

    If `vendor_client` is provided, each round's vendor offer is
    fetched over real HTTP from that vendor's genuinely separate service
    (PRD §17) -- the negotiation actually happens across process/service
    boundaries, not just in-process math. Without it (e.g. fast unit/e2e
    tests against fixtures), offers are computed in-process using the same
    deterministic function the vendor services call internally -- the math
    is identical either way; only the transport differs.

    Composes `run_discovery_phase` and `run_negotiation_and_decision_phase`
    -- the same two phase functions `pact/adk/pipeline.py` runs as real,
    separately-scheduled ADK agents. This function is the direct in-process
    composition (used by the live API, CLI, and every test); the ADK
    pipeline is a genuine, additional way to run the identical logic
    through ADK's Runner/session/event machinery, not a replacement for it."""
    state = NegotiationState(
        negotiation_id=negotiation_id or str(uuid.uuid4()),
        requirement=requirement,
        policy=policy,
    )
    state.log(EventType.REQUIREMENT_RECEIVED, detail=requirement.raw_input)

    run_discovery_phase(state, candidate_vendors, agent_cards)
    if not state.active_vendors:
        return state

    run_negotiation_and_decision_phase(
        state,
        requirement,
        policy,
        agent_cards,
        pricing_source,
        initial_claimed_discounts,
        max_rounds=max_rounds,
        vendor_client=vendor_client,
        narrator=narrator,
        plausibility_screener=plausibility_screener,
        compliance_client=compliance_client,
    )
    return state
