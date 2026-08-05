"""Real Google ADK orchestration for Pact's pipeline (PRD §11's Google
Technology Stack table). Runs the exact same, already-tested phase
functions from `pact/orchestration/graph.py` -- `run_discovery_phase` and
`run_negotiation_and_decision_phase` -- as two genuinely separate ADK
agents, composed via a real `SequentialAgent` and executed through a real
ADK `Runner` + `InMemorySessionService`.

This is an additional, honest way to run the identical negotiation logic
-- not a replacement for `orchestration.graph.run_negotiation`, which
remains the pipeline the live API, CLI, and every test use directly (the
same relationship MCP's server has to the plain-Python tool logic it
wraps: one source of truth, exposed through a real protocol/framework
without being duplicated).

Domain state (the `NegotiationState` object, requirement, policy, etc.)
is passed to each ADK agent as a declared pydantic field at construction
time rather than through ADK's session `state` dict, because ADK's
`Runner` does not expose the live, in-run session object back to the
caller -- session state changes are only visible to sibling agents
*during* that one run, not to code outside it (verified directly: a
mutation to `ctx.session.state` inside an agent is not visible on the
`Session` object `create_session` returned, nor via a fresh
`get_session` call afterward). Holding the actual `NegotiationState`
object by reference sidesteps that entirely and needs no re-serialization
of its rich types (enums, datetimes, nested Pydantic models)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import ConfigDict

from pact.a2a.vendor_client import HttpVendorClient
from pact.agents import decision_agent
from pact.mcp_tools.pricing_tool import PricingSource
from pact.mcp_tools.verification_tool import PlausibilityScreener
from pact.models.schemas import AgentCard, PolicyConstraints, Requirement, VendorId
from pact.orchestration.graph import (
    DEFAULT_MAX_ROUNDS,
    run_discovery_phase,
    run_negotiation_and_decision_phase,
)
from pact.orchestration.state import EventType, NegotiationState


class _DiscoveryPhaseAgent(BaseAgent):
    """Real ADK agent wrapping the Discovery Agent phase (FR-2)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    state: NegotiationState
    candidate_vendors: list[VendorId]
    agent_cards: dict[VendorId, AgentCard]

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        events_before = len(self.state.events)
        run_discovery_phase(self.state, self.candidate_vendors, self.agent_cards)
        for event in self.state.events[events_before:]:
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=f"{event.event_type.value}: {event.detail}")]),
            )


class _NegotiationDecisionPhaseAgent(BaseAgent):
    """Real ADK agent wrapping Negotiation -> Verification -> Compliance ->
    Comparison -> Decision (PRD §19). Requires the Discovery phase to have
    already populated `state.active_vendors`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    state: NegotiationState
    requirement: Requirement
    policy: PolicyConstraints
    agent_cards: dict[VendorId, AgentCard]
    pricing_source: object  # PricingSource -- a Protocol, not isinstance-checkable by pydantic
    initial_claimed_discounts: dict[VendorId, float]
    max_rounds: int = DEFAULT_MAX_ROUNDS
    vendor_client: HttpVendorClient | None = None
    narrator: decision_agent.Narrator | None = None
    plausibility_screener: PlausibilityScreener | None = None

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not self.state.active_vendors:
            return
        events_before = len(self.state.events)
        run_negotiation_and_decision_phase(
            self.state,
            self.requirement,
            self.policy,
            self.agent_cards,
            self.pricing_source,
            self.initial_claimed_discounts,
            max_rounds=self.max_rounds,
            vendor_client=self.vendor_client,
            narrator=self.narrator,
            plausibility_screener=self.plausibility_screener,
        )
        for event in self.state.events[events_before:]:
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=f"{event.event_type.value}: {event.detail}")]),
            )


async def run_negotiation_via_adk(
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
) -> NegotiationState:
    """Runs the identical negotiation logic as `graph.run_negotiation`, but
    through a real ADK `SequentialAgent` under a real ADK `Runner`. Returns
    the same `NegotiationState` shape either way."""
    state = NegotiationState(
        negotiation_id=str(uuid.uuid4()),
        requirement=requirement,
        policy=policy,
    )
    state.log(EventType.REQUIREMENT_RECEIVED, detail=requirement.raw_input)

    pipeline = SequentialAgent(
        name="pact_pipeline",
        sub_agents=[
            _DiscoveryPhaseAgent(
                name="discovery_agent",
                state=state,
                candidate_vendors=candidate_vendors,
                agent_cards=agent_cards,
            ),
            _NegotiationDecisionPhaseAgent(
                name="negotiation_decision_agent",
                state=state,
                requirement=requirement,
                policy=policy,
                agent_cards=agent_cards,
                pricing_source=pricing_source,
                initial_claimed_discounts=initial_claimed_discounts,
                max_rounds=max_rounds,
                vendor_client=vendor_client,
                narrator=narrator,
                plausibility_screener=plausibility_screener,
            ),
        ],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="pact", user_id="pact-buyer-agent")
    runner = Runner(app_name="pact", agent=pipeline, session_service=session_service)
    opening_message = types.Content(role="user", parts=[types.Part(text=requirement.raw_input)])
    async for _adk_event in runner.run_async(
        user_id="pact-buyer-agent", session_id=session.id, new_message=opening_message
    ):
        pass  # each yielded ADK Event mirrors a real NegotiationState log entry (see agents above)

    return state
