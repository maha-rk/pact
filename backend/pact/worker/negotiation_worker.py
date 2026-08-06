"""The Negotiation Worker: an independently deployable, horizontally
scalable process (`python -m pact.worker.negotiation_worker`) that pulls
negotiation-request messages off a real Google Cloud Pub/Sub subscription
and runs the same, unmodified `run_negotiation` pipeline
(`pact/orchestration/graph.py`) per message -- the piece that makes
negotiation execution genuinely decoupled from the API process, closing
the architecture review's "single-process orchestration" gap.

Only used when `PACT_DISTRIBUTED=true`; the API's default `in_process`
path never touches this module (see `pact/api/routes_negotiation.py`).

Redelivery safety: because `run_negotiation` is deterministic (the same
reproducibility guarantee `tests/e2e/test_flagship_scenario.py` proves
for the in-process path) and the store write is an idempotent `.set()`,
Pub/Sub's at-least-once redelivery is safe by construction -- a
redelivered message just recomputes and overwrites the same terminal
state. This is genuine fault isolation: a worker crash mid-run now
redelivers to another instance instead of just breaking one HTTP
request, which is what happens in the in-process path today."""

from __future__ import annotations

import json
import logging
import os

from pact import runtime_factories
from pact.a2a.compliance_client import HttpComplianceClient
from pact.a2a.verification_client import HttpVerificationClient
from pact.messaging import pubsub_client
from pact.models.schemas import AgentCard, PolicyConstraints, Requirement, VendorId
from pact.orchestration.graph import run_negotiation
from pact.store.negotiation_store import FirestoreStore

logger = logging.getLogger("pact.negotiation_worker")

COMPLIANCE_SERVICE_ENDPOINT = os.environ.get("PACT_COMPLIANCE_SERVICE_URL", "http://localhost:9101")
VERIFICATION_SERVICE_ENDPOINT = os.environ.get("PACT_VERIFICATION_SERVICE_URL", "http://localhost:9102")

VENDOR_ENDPOINTS = {
    VendorId.AWS: "http://localhost:9001",
    VendorId.AZURE: "http://localhost:9002",
}
AGENT_CARDS = {
    vid: AgentCard(vendor_id=vid, name=f"{vid.value.upper()} Vendor Agent", endpoint=ep, capabilities=["negotiate"])
    for vid, ep in VENDOR_ENDPOINTS.items()
}


def _handle_message(message) -> None:
    negotiation_id = "<undecoded>"
    try:
        payload = json.loads(message.data.decode("utf-8"))
        negotiation_id = payload["negotiation_id"]

        requirement = Requirement(
            gpu_type=payload.get("gpu_type", "H100"),
            gpu_count=payload["gpu_count"],
            contract_months=payload["contract_months"],
            budget_ceiling_usd=payload["budget_ceiling_usd"],
            region=payload.get("region"),
            raw_input=payload["raw_input"],
        )
        policy = PolicyConstraints(
            budget_ceiling_usd=payload["budget_ceiling_usd"],
            blocked_vendors=[VendorId(v) for v in payload.get("blocked_vendors", [])],
            required_certifications=payload.get("required_certifications", []),
        )
        initial_claimed_discounts = {VendorId(v): rate for v, rate in payload["initial_claimed_discounts"].items()}
        candidate_vendors = list(initial_claimed_discounts.keys())

        state = run_negotiation(
            requirement=requirement,
            policy=policy,
            candidate_vendors=candidate_vendors,
            agent_cards={v: AGENT_CARDS[v] for v in candidate_vendors},
            pricing_source=runtime_factories.pricing_source(),
            initial_claimed_discounts=initial_claimed_discounts,
            vendor_client=runtime_factories.vendor_client(VENDOR_ENDPOINTS),
            narrator=runtime_factories.narrator(),
            plausibility_screener=runtime_factories.plausibility_screener(),
            compliance_client=HttpComplianceClient(COMPLIANCE_SERVICE_ENDPOINT),
            verification_client=HttpVerificationClient(VERIFICATION_SERVICE_ENDPOINT),
            negotiation_id=negotiation_id,
        )
        FirestoreStore().save(state)
        logger.info("Negotiation %s completed with status %s", negotiation_id, state.status.value)
        message.ack()
    except Exception:
        logger.exception("Failed to process negotiation %s; leaving unacked for redelivery", negotiation_id)
        message.nack()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pubsub_client.ensure_topic_and_subscription()
    future = pubsub_client.subscribe(_handle_message)
    logger.info("Negotiation worker listening on %s", pubsub_client.subscription_path())
    try:
        future.result()
    except KeyboardInterrupt:
        future.cancel()
        future.result()


if __name__ == "__main__":
    main()
