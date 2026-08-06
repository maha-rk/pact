"""Proves the evidence hash (pact/security/evidence_hash.py) is what it
claims to be: identical negotiation inputs produce an identical hash
regardless of wall-clock time, and any real change to the evidence trail
changes the hash. Extends the same reproducibility guarantee
tests/e2e/test_flagship_scenario.py::test_reproducibility_identical_inputs_identical_outcome
already proves for offers and the decision, into an artifact a third
party can independently check."""

from __future__ import annotations

import time

from pact.models.schemas import AgentCard, VendorId
from pact.orchestration.graph import run_negotiation
from pact.security.evidence_hash import compute_evidence_hash, evidence_bundle
from tests.fixtures import FLAGSHIP_CLAIMED_DISCOUNTS, FixturePricingSource, flagship_policy, flagship_requirement

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


def test_a_completed_negotiation_carries_a_real_sha256_hash():
    state = _run()
    assert state.evidence_hash is not None
    assert len(state.evidence_hash) == 64  # SHA-256 hex digest length
    int(state.evidence_hash, 16)  # raises ValueError if not valid hex


def test_identical_inputs_produce_an_identical_hash_regardless_of_when_they_ran():
    """The actual claim this feature makes: not that live pricing never
    changes over time (it can), but that two runs of identical
    negotiation logic against identical inputs produce a byte-identical
    evidence hash, proving the hash isn't accidentally keyed to wall
    clock time (e.g. via an unstripped timestamp field)."""
    first = _run()
    time.sleep(1.1)  # force a real, measurable wall-clock gap between runs
    second = _run()

    assert first.evidence_hash == second.evidence_hash
    # And the underlying bundle a verifier would actually recompute from
    # is identical too, not just the hash by coincidence.
    assert evidence_bundle(first) == evidence_bundle(second)


def test_a_real_change_to_the_evidence_trail_changes_the_hash():
    """The negative case: this must not be a hash that stays constant
    regardless of content (which would make it worthless as tamper
    evidence)."""
    state = _run()
    original_hash = state.evidence_hash

    # Mutate something a verifier would actually care about catching.
    state.decision.final_price_usd = state.decision.final_price_usd + 1.0
    tampered_hash = compute_evidence_hash(state)

    assert tampered_hash != original_hash


def test_the_exported_bundle_independently_recomputes_to_the_stored_hash():
    """What GET /negotiations/{id}/evidence actually promises: take the
    bundle it returns, hash it yourself, and it matches the hash
    displayed in the UI -- proving the record wasn't altered in transit
    or at rest."""
    state = _run()
    bundle = evidence_bundle(state)

    import hashlib
    import json

    recomputed = hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert recomputed == state.evidence_hash
