"""A real hash CHAIN over a negotiation's event log -- a different
mechanism from, and complementary to, the whole-bundle fingerprint in
`evidence_hash.py`.

`evidence_hash.py` is deliberately timestamp-free: its job is to prove
two runs with identical negotiation logic produce byte-identical
evidence, and it's only computed once, at a terminal state. This module
does the opposite job on purpose: each event's chain hash incorporates
its own real timestamp and the previous event's chain hash, so it can
prove THIS SPECIFIC negotiation's sequence of events happened in this
exact order, at these exact times, and that no event was inserted,
removed, reordered, or altered after the fact -- updated incrementally
as each event is logged, so a negotiation's integrity is verifiable
even while it's still in progress, not just once it reaches a terminal
state.

Tampering with any single event changes that event's own chain hash and
every one after it -- the standard tamper-evidence property of a hash
chain (the same principle git commits and blockchains use), applied
here to one negotiation's own audit log. `tests/unit/test_audit_chain.py`
proves this for real: mutating an early event and recomputing the chain
changes the final chain head, not just the mutated event's own hash."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pact.orchestration.state import NegotiationEvent

GENESIS_HASH = hashlib.sha256(b"PACT_AUDIT_CHAIN_GENESIS").hexdigest()
"""Fixed starting point for every chain -- not secret, just a
deterministic seed so an empty event log has a well-defined chain state
rather than a null/undefined one."""


def _event_canonical(event: "NegotiationEvent") -> dict:
    return {
        "event_type": event.event_type.value,
        "vendor_id": event.vendor_id.value if event.vendor_id else None,
        "round_number": event.round_number,
        "detail": event.detail,
        "timestamp": event.timestamp.isoformat(),
    }


def chain_link(previous_hash: str, event: "NegotiationEvent") -> str:
    """The next link in the chain: SHA-256 over the previous link's hash
    concatenated with this event's own canonical (sorted-key, no
    whitespace) JSON. Call once per event, in the order events actually
    occurred -- `NegotiationState.log()` does this automatically."""
    canonical = json.dumps(_event_canonical(event), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((previous_hash + canonical).encode("utf-8")).hexdigest()


def recompute_chain(events: list["NegotiationEvent"]) -> list[str]:
    """Recomputes the full chain from a real event list, independent of
    whatever `chain_hash` each event already carries -- used to verify
    an exported or reloaded record wasn't tampered with, by comparing
    this against the stored per-event hashes."""
    hashes: list[str] = []
    previous = GENESIS_HASH
    for event in events:
        previous = chain_link(previous, event)
        hashes.append(previous)
    return hashes
