"""Proves the audit chain (pact/security/audit_chain.py) is a real hash
chain, not just N independent per-event hashes: tampering with one
event changes every chain hash from that point forward, and the chain
is built incrementally by NegotiationState.log() itself, not as a
separate post-hoc step -- so a negotiation's integrity is checkable
even while it's still in progress."""

from __future__ import annotations

from pact.models.schemas import AgentCard, VendorId
from pact.orchestration.graph import run_negotiation
from pact.security.audit_chain import GENESIS_HASH, chain_link, recompute_chain
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


def test_every_logged_event_carries_a_real_chain_hash():
    state = _run()
    assert len(state.events) > 5  # sanity: a real multi-round negotiation logged something
    for event in state.events:
        assert event.chain_hash is not None
        assert len(event.chain_hash) == 64
        int(event.chain_hash, 16)  # raises ValueError if not valid hex


def test_the_chain_is_built_incrementally_not_independently():
    """The actual "chain" property: each event's hash depends on the
    previous event's hash, not just its own content -- so two identical
    events at different positions in the log get different chain hashes."""
    state = _run()
    hashes = [e.chain_hash for e in state.events]
    assert len(hashes) == len(set(hashes))  # no two events share a chain hash

    # The first event's chain hash must depend on GENESIS_HASH.
    first = state.events[0]
    assert first.chain_hash == chain_link(GENESIS_HASH, first)

    # Every later event's chain hash must depend on its predecessor's.
    for i in range(1, len(state.events)):
        assert state.events[i].chain_hash == chain_link(state.events[i - 1].chain_hash, state.events[i])


def test_recompute_chain_matches_the_stored_per_event_hashes():
    """What a verifier actually does: take the real event log, recompute
    the chain from scratch, and confirm it matches what was stored."""
    state = _run()
    recomputed = recompute_chain(state.events)
    assert recomputed == [e.chain_hash for e in state.events]


def test_tampering_with_an_early_event_changes_every_later_chain_hash():
    """The property that makes this a chain rather than a list of
    unrelated hashes: mutating one event invalidates its own hash AND
    every hash after it, not just the one that was changed."""
    state = _run()
    original_hashes = [e.chain_hash for e in state.events]
    assert len(state.events) >= 3  # need real events before/after the tamper point

    tamper_index = 1
    state.events[tamper_index].detail = state.events[tamper_index].detail + " (tampered)"
    recomputed = recompute_chain(state.events)

    # Everything from the tamper point onward must now mismatch.
    for i in range(tamper_index, len(state.events)):
        assert recomputed[i] != original_hashes[i]
    # Everything strictly before the tamper point is unaffected.
    for i in range(tamper_index):
        assert recomputed[i] == original_hashes[i]


def test_an_empty_event_log_has_no_chain_head():
    assert recompute_chain([]) == []
