"""Discovery Agent: finds Vendor Agents and verifies their declared
identity before negotiation begins (PRD FR-2, §17). Bounded to what an A2A
Agent Card already provides -- not a from-scratch trust/PKI system."""

from __future__ import annotations

from pact.models.schemas import AgentCard


def verify_agent_card(card: AgentCard) -> bool:
    return bool(card.name and card.endpoint and card.capabilities)
