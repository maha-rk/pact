"""Shared `NegotiationState` store: `InProcessStore` (today's exact
single-process dict, used when `PACT_DISTRIBUTED` is off) and
`FirestoreStore` (real Firestore Native-mode client, respects
`FIRESTORE_EMULATOR_HOST` automatically) -- the shared read/write surface
the API and the independently-deployed worker both need once negotiation
execution runs in a separate process from the one that serves
`GET /negotiations/{id}`.

Firestore was chosen over BigQuery (see `pact/logging/bigquery_sink.py`'s
deliberate batch-load design -- the wrong latency/consistency model for a
bounded-poll read-after-write) and over a third, differently-shaped new
dependency for a simple KV store (no official GCS emulator exists in the
same `gcloud emulators` family Pub/Sub already uses here)."""

from __future__ import annotations

import json
import os
from typing import Protocol

from pact.orchestration.state import NegotiationState


class NegotiationStore(Protocol):
    def save(self, state: NegotiationState) -> None: ...
    def load(self, negotiation_id: str) -> NegotiationState | None: ...
    def list_all(self) -> list[NegotiationState]: ...


class InProcessStore:
    """Today's exact behavior: a plain in-process dict. Only correct when
    the API and negotiation execution share one process
    (`PACT_DISTRIBUTED` unset/false, the default)."""

    def __init__(self) -> None:
        self._data: dict[str, NegotiationState] = {}

    def save(self, state: NegotiationState) -> None:
        self._data[state.negotiation_id] = state

    def load(self, negotiation_id: str) -> NegotiationState | None:
        return self._data.get(negotiation_id)

    def list_all(self) -> list[NegotiationState]:
        return list(self._data.values())


PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "pact-hackathon")
COLLECTION = "negotiations"

_client = None


def _get_client():
    global _client
    if _client is None:
        from google.cloud import firestore

        _client = firestore.Client(project=PROJECT_ID)
    return _client


def is_configured() -> bool:
    try:
        _get_client()
        return True
    except Exception:
        return False


class FirestoreStore:
    """Real Firestore Native-mode store -- the shared state the API
    bounded-polls and the worker writes to, once they're genuinely
    separate, independently deployable processes connected only by
    Pub/Sub + this store."""

    def save(self, state: NegotiationState) -> None:
        client = _get_client()
        client.collection(COLLECTION).document(state.negotiation_id).set(
            json.loads(state.model_dump_json())
        )

    def load(self, negotiation_id: str) -> NegotiationState | None:
        client = _get_client()
        doc = client.collection(COLLECTION).document(negotiation_id).get()
        if not doc.exists:
            return None
        return NegotiationState.model_validate(doc.to_dict())

    def list_all(self) -> list[NegotiationState]:
        client = _get_client()
        return [NegotiationState.model_validate(doc.to_dict()) for doc in client.collection(COLLECTION).stream()]
