"""Real Google Cloud Pub/Sub wiring for the API -> Worker negotiation
dispatch. This is what makes negotiation execution genuinely decoupled
from the API process: `pact/api/routes_negotiation.py` publishes here,
`pact/worker/negotiation_worker.py` (a separately deployable process)
pulls from here -- the API and worker communicate only through this
module, never through shared memory.

Respects `PUBSUB_EMULATOR_HOST` automatically -- the official
`google-cloud-pubsub` client library honors that env var itself, so tests
and CI point this at a local emulator with zero branching here; only
`GCP_PROJECT_ID` differs between the emulator and a live deployment.

Publishing raises on failure (unlike `bigquery_sink.py`'s never-raises
discipline) -- a silently dropped negotiation-request message isn't a
degraded nice-to-have, it's the entire job never running."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("pact.pubsub_client")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "pact-hackathon")
TOPIC_ID = "negotiation-requests"
SUBSCRIPTION_ID = "negotiation-requests-worker"

_publisher = None
_subscriber = None


def _get_publisher():
    global _publisher
    if _publisher is None:
        from google.cloud import pubsub_v1

        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def _get_subscriber():
    global _subscriber
    if _subscriber is None:
        from google.cloud import pubsub_v1

        _subscriber = pubsub_v1.SubscriberClient()
    return _subscriber


def topic_path() -> str:
    return _get_publisher().topic_path(PROJECT_ID, TOPIC_ID)


def subscription_path() -> str:
    return _get_subscriber().subscription_path(PROJECT_ID, SUBSCRIPTION_ID)


def is_configured() -> bool:
    try:
        _get_publisher()
        return True
    except Exception:
        return False


def subscribe(callback):
    """Starts a real, blocking-until-cancelled pull subscription (not
    push -- the worker, like the vendor services, is intentionally never
    publicly reachable, so a push subscription's requirement for a public
    HTTPS callback URL doesn't fit this topology). Returns the
    `StreamingPullFuture`; call `.result()` to block, `.cancel()` to stop."""
    subscriber = _get_subscriber()
    return subscriber.subscribe(subscription_path(), callback=callback)


def ensure_topic_and_subscription() -> None:
    """Create-if-missing. The Pub/Sub emulator starts with no topics, and
    a fresh real project has none either -- called from worker/test
    startup so no separate manual provisioning step is required."""
    from google.api_core.exceptions import AlreadyExists

    publisher, subscriber = _get_publisher(), _get_subscriber()
    try:
        publisher.create_topic(request={"name": topic_path()})
    except AlreadyExists:
        pass
    try:
        subscriber.create_subscription(request={"name": subscription_path(), "topic": topic_path()})
    except AlreadyExists:
        pass


def publish_negotiation_requested(negotiation_id: str, payload: dict) -> None:
    """Publishes the full negotiation request (the already-validated
    request body plus the pre-minted `negotiation_id`) for a worker to
    pick up. Raises on failure -- the caller
    (`routes_negotiation.py::create_negotiation`) must not treat a
    dropped dispatch as a successfully submitted negotiation."""
    publisher = _get_publisher()
    message = {"negotiation_id": negotiation_id, **payload}
    future = publisher.publish(topic_path(), json.dumps(message).encode("utf-8"))
    future.result(timeout=10.0)  # raises on failure; blocks until acked by the broker
    logger.info("Published negotiation.requested for %s", negotiation_id)
