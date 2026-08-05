"""Human approval gate (PRD FR-8). This is the ONLY function in the
codebase permitted to set a negotiation's status to FINALIZED -- FR-8's
acceptance criteria is literal: no other code path may finalize a binding
commitment."""

from __future__ import annotations

from datetime import UTC, datetime

from pact.orchestration.state import EventType, NegotiationState, NegotiationStatus


def approve(state: NegotiationState, approved_by: str) -> NegotiationState:
    if state.status != NegotiationStatus.AGREED_PENDING_APPROVAL:
        raise ValueError(f"Cannot approve a negotiation in status {state.status}")
    if state.decision is None:
        raise ValueError("No decision to approve")

    state.decision.approved = True
    state.decision.approved_at = datetime.now(UTC)
    state.status = NegotiationStatus.FINALIZED
    state.log(EventType.DECISION_APPROVED, detail=f"Approved by {approved_by}")
    return state
