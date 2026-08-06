"""A real, independently verifiable SHA-256 fingerprint over a
negotiation's full evidence trail -- requirement, policy, every offer,
every verification and compliance check, the full event log, and the
final decision. Not a badge asserting integrity; a hash anyone can
recompute from an exported record and compare.

Deliberately excludes wall-clock-dependent fields (timestamps): two
negotiations with identical inputs and identical negotiation logic must
produce an identical hash regardless of when either one actually ran,
which is what makes `tests/unit/test_evidence_hash.py`'s "identical
inputs -> identical hash" assertion meaningful rather than vacuous. This
is an extension of the same reproducibility guarantee
`tests/e2e/test_flagship_scenario.py::test_reproducibility_identical_inputs_identical_outcome`
already proves for offers and the decision -- made into an artifact a
third party can check without re-running anything.

Honest scope note: this is not a claim that re-running against *live*
external pricing will always reproduce the same hash forever -- real
vendor prices can genuinely change over time, and Gemini's narration
text is not itself deterministic. What this hash actually proves is
narrower and more useful: given one specific logged record, anyone can
recompute its hash from the exported evidence bundle
(`GET /negotiations/{id}/evidence`) and confirm it matches what was
originally produced -- i.e. that the record has not been altered since."""

from __future__ import annotations

import hashlib
import json

from pact.orchestration.state import NegotiationState


def evidence_bundle(state: NegotiationState) -> dict:
    """The canonical, decision-relevant content the evidence hash is
    computed over. Every field here is either a user-supplied input, a
    value fetched from a real external source, or the output of
    deterministic logic -- never a random or wall-clock-dependent value.

    Deliberately excludes `negotiation_id`: it's a randomly generated
    database key, not evidence content, so two negotiations with
    byte-identical requirement/offers/verification/compliance/decision
    content are correctly recognized as carrying identical evidence even
    though each was assigned a different ID -- caught for real by this
    module's own test suite, which initially failed because two runs of
    the same fixture scenario got different hashes purely from each
    minting its own random ID, not from any actual difference in the
    negotiation itself."""
    return {
        "requirement": state.requirement.model_dump(mode="json"),
        "policy": state.policy.model_dump(mode="json"),
        "status": state.status.value,
        "offers": [
            {
                "vendor_id": o.vendor_id.value,
                "round_number": o.round_number,
                "price_usd": o.price_usd,
                "claimed_discount_rate": o.claimed_discount_rate,
            }
            for o in state.offers
        ],
        "verification_results": [
            {
                "vendor_id": r.vendor_id.value,
                "claim_checked": r.claim_checked,
                "claimed_value": r.claimed_value,
                "actual_value": r.actual_value,
                "source": r.source,
                "matched": r.matched,
            }
            for r in state.verification_results
        ],
        "compliance_results": [
            {
                "vendor_id": c.vendor_id.value,
                "constraint_name": c.constraint_name,
                "passed": c.passed,
                "detail": c.detail,
            }
            for c in state.compliance_results
        ],
        "events": [
            {
                "event_type": e.event_type.value,
                "vendor_id": e.vendor_id.value if e.vendor_id else None,
                "round_number": e.round_number,
                "detail": e.detail,
            }
            for e in state.events
        ],
        "decision": None
        if state.decision is None
        else {
            "selected_vendor": state.decision.selected_vendor.value if state.decision.selected_vendor else None,
            "final_price_usd": state.decision.final_price_usd,
            "evidence": [{"label": ev.label, "value": ev.value, "source": ev.source} for ev in state.decision.evidence],
            "reasoning": state.decision.reasoning,
        },
    }


def compute_evidence_hash(state: NegotiationState) -> str:
    """Real SHA-256 over a canonical (sorted-key, no whitespace) JSON
    serialization of `evidence_bundle(state)`."""
    canonical = json.dumps(evidence_bundle(state), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
