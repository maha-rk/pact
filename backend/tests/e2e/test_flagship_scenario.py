"""End-to-end validation of the PRD's Flagship Demonstration Scenario
(§18) against fixture data: both "wow" moments must actually happen, not
just be narratable -- and the whole thing must be reproducible (FR-4)."""

from pact.models.schemas import AgentCard, VendorId
from pact.orchestration import approval
from pact.orchestration.graph import run_negotiation
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


def _run():
    return run_negotiation(
        requirement=flagship_requirement(),
        policy=flagship_policy(),
        candidate_vendors=CANDIDATE_VENDORS,
        agent_cards=AGENT_CARDS,
        pricing_source=FixturePricingSource(),
        initial_claimed_discounts=dict(FLAGSHIP_CLAIMED_DISCOUNTS),
    )


def test_wow_moment_1_aws_claim_caught_and_rejected():
    state = _run()
    aws_rejections = [
        r for r in state.verification_results if r.vendor_id == VendorId.AWS and not r.matched
    ]
    assert aws_rejections, "AWS's inflated claim must be caught by the Verification Agent"
    assert aws_rejections[0].claimed_value == 0.25
    assert aws_rejections[0].actual_value == 0.0  # no <1yr committed-use tier exists, per real AWS data

    reject_events = [e for e in state.events if e.event_type == EventType.CLAIM_REJECTED]
    renegotiate_events = [e for e in state.events if e.event_type == EventType.RENEGOTIATION_TRIGGERED]
    assert reject_events, "A CLAIM_REJECTED event must be logged"
    assert renegotiate_events, "A RENEGOTIATION_TRIGGERED event must follow the rejection"


def test_wow_moment_2_compliance_rejects_a_verified_offer():
    state = _run()
    compliance_rejections = [c for c in state.compliance_results if not c.passed]
    assert compliance_rejections, "At least one verified offer must still be rejected on compliance grounds"
    for rejection in compliance_rejections:
        assert rejection.constraint_name == "budget_ceiling"


def test_azure_wins_with_a_verified_compliant_deal():
    state = _run()
    assert state.status == NegotiationStatus.AGREED_PENDING_APPROVAL
    assert state.decision is not None
    assert state.decision.selected_vendor == VendorId.AZURE
    assert state.decision.final_price_usd is not None
    assert state.decision.final_price_usd <= state.policy.budget_ceiling_usd
    # every evidence item traces to a real, cited source (NFR: accuracy of grounding)
    assert len(state.decision.evidence) >= 1
    for item in state.decision.evidence:
        assert item.source


def test_deal_is_not_finalized_without_explicit_approval():
    state = _run()
    assert state.status == NegotiationStatus.AGREED_PENDING_APPROVAL
    assert state.decision.approved is False
    assert state.decision.approved_at is None


def test_approval_is_the_only_path_to_finalization():
    state = _run()
    approval.approve(state, approved_by="test-user")
    assert state.status == NegotiationStatus.FINALIZED
    assert state.decision.approved is True
    assert state.decision.approved_at is not None
    approved_events = [e for e in state.events if e.event_type == EventType.DECISION_APPROVED]
    assert approved_events


def test_reproducibility_identical_inputs_identical_outcome():
    """NFR: given the same inputs, the negotiation produces the same
    sequence of offers and the same final decision."""
    first = _run()
    second = _run()
    assert [o.price_usd for o in first.offers] == [o.price_usd for o in second.offers]
    assert first.decision.selected_vendor == second.decision.selected_vendor
    assert first.decision.final_price_usd == second.decision.final_price_usd
