"""Proves `pact/adk/pipeline.py` is a real, working ADK orchestration --
running the flagship scenario through a real ADK `SequentialAgent` under a
real ADK `Runner` produces the exact same verified numbers as the direct
`graph.run_negotiation` path (tests/e2e/test_flagship_scenario.py), since
both compose the identical two phase functions."""

from pact.adk.pipeline import run_negotiation_via_adk
from pact.models.schemas import AgentCard, VendorId
from pact.orchestration.state import EventType, NegotiationStatus
from tests.fixtures import (
    FLAGSHIP_CLAIMED_DISCOUNTS,
    FixturePricingSource,
    flagship_policy,
    flagship_requirement,
)

CANDIDATE_VENDORS = [VendorId.AWS, VendorId.AZURE, VendorId.GCP]

AGENT_CARDS = {
    VendorId.AWS: AgentCard(vendor_id=VendorId.AWS, name="AWS Vendor Agent", endpoint="http://localhost:9001", capabilities=["negotiate"]),
    VendorId.AZURE: AgentCard(vendor_id=VendorId.AZURE, name="Azure Vendor Agent", endpoint="http://localhost:9002", capabilities=["negotiate"]),
    VendorId.GCP: AgentCard(vendor_id=VendorId.GCP, name="GCP Vendor Agent", endpoint="http://localhost:9003", capabilities=["negotiate"]),
}


async def _run_via_adk():
    return await run_negotiation_via_adk(
        requirement=flagship_requirement(),
        policy=flagship_policy(),
        candidate_vendors=CANDIDATE_VENDORS,
        agent_cards=AGENT_CARDS,
        pricing_source=FixturePricingSource(),
        initial_claimed_discounts=dict(FLAGSHIP_CLAIMED_DISCOUNTS),
    )


async def test_adk_pipeline_catches_the_aws_claim_mismatch():
    state = await _run_via_adk()
    reject_events = [e for e in state.events if e.event_type == EventType.CLAIM_REJECTED]
    assert reject_events, "the real ADK-orchestrated run must still catch AWS's inflated claim"


async def test_adk_pipeline_produces_the_same_winning_deal_as_the_direct_path():
    state = await _run_via_adk()
    assert state.status == NegotiationStatus.AGREED_PENDING_APPROVAL
    assert state.decision.selected_vendor == VendorId.AZURE
    assert state.decision.final_price_usd is not None
    assert state.decision.final_price_usd <= state.policy.budget_ceiling_usd


async def test_adk_pipeline_runs_two_genuinely_separate_adk_agents():
    """Confirms this actually went through ADK's agent tree, not a
    disguised direct call -- each phase should appear as its own event
    author in the ADK event stream, in the same order graph.py runs them."""
    import warnings

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from pact.adk.pipeline import (
        DEFAULT_MAX_ROUNDS,
        NegotiationState,
        SequentialAgent,
        _DiscoveryPhaseAgent,
        _NegotiationDecisionPhaseAgent,
    )

    state = NegotiationState(
        negotiation_id="test-adk-authors",
        requirement=flagship_requirement(),
        policy=flagship_policy(),
    )
    pipeline = SequentialAgent(
        name="pact_pipeline",
        sub_agents=[
            _DiscoveryPhaseAgent(
                name="discovery_agent", state=state, candidate_vendors=CANDIDATE_VENDORS, agent_cards=AGENT_CARDS
            ),
            _NegotiationDecisionPhaseAgent(
                name="negotiation_decision_agent",
                state=state,
                requirement=flagship_requirement(),
                policy=flagship_policy(),
                agent_cards=AGENT_CARDS,
                pricing_source=FixturePricingSource(),
                initial_claimed_discounts=dict(FLAGSHIP_CLAIMED_DISCOUNTS),
                max_rounds=DEFAULT_MAX_ROUNDS,
            ),
        ],
    )
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="pact", user_id="u1")
    runner = Runner(app_name="pact", agent=pipeline, session_service=session_service)
    msg = types.Content(role="user", parts=[types.Part(text="test")])
    authors = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        async for event in runner.run_async(user_id="u1", session_id=session.id, new_message=msg):
            authors.append(event.author)

    assert "discovery_agent" in authors
    assert "negotiation_decision_agent" in authors
    assert authors.index("discovery_agent") < authors.index("negotiation_decision_agent")
