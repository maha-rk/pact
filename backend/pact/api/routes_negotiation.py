"""The pact-core API: what the frontend and the demo actually talk to.
Both required UI surfaces (PRD §22, FR-10) read GET /negotiations/{id}
and render two projections of the same record.

Two execution modes, selected by `_execution_mode()`:
- `in_process` (default): today's exact synchronous behavior -- a
  negotiation runs to completion inside this request, in this process.
  Zero new infrastructure required; every existing test exercises this
  path unchanged.
- `distributed` (`PACT_DISTRIBUTED=true`, and only if Pub/Sub/Firestore
  are actually reachable -- probed, not trusted, exactly like
  `_plausibility_screener()`): negotiation execution happens in a
  separately deployable worker process
  (`pact/worker/negotiation_worker.py`), dispatched over real Google
  Cloud Pub/Sub. `POST /negotiations` still returns the complete final
  `NegotiationState` synchronously for the normal (sub-second) case, via
  a bounded poll of the shared Firestore store -- the frontend's existing
  contract is unchanged. See docs/ARCHITECTURE.md for the full
  disclosure."""

from __future__ import annotations

import logging
import os
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from pact import runtime_factories
from pact.a2a.vendor_client import HttpVendorClient
from pact.api.gateway import limiter, require_bearer_token
from pact.logging import bigquery_sink
from pact.messaging import pubsub_client
from pact.models.schemas import AgentCard, PolicyConstraints, Requirement, VendorId
from pact.orchestration import approval
from pact.orchestration.graph import run_negotiation
from pact.orchestration.state import EventType, NegotiationState, NegotiationStatus
from pact.security.evidence_hash import evidence_bundle
from pact.store import negotiation_store
from pact.store.negotiation_store import FirestoreStore, InProcessStore

logger = logging.getLogger("pact.routes_negotiation")

router = APIRouter(prefix="/negotiations", tags=["negotiations"])

# Backing store for the in_process execution mode -- today's exact
# behavior (a plain in-process dict, wrapped). Must be a module-level
# singleton, reused across requests, not recreated per call.
_in_process_store = InProcessStore()

VENDOR_ENDPOINTS = {
    VendorId.AWS: "http://localhost:9001",
    VendorId.AZURE: "http://localhost:9002",
}
# Mirrors each vendor's own self-declared AGENT_CARD (vendors/*/app.py) --
# live A2A discovery (HttpVendorClient.get_agent_card) exists but isn't
# wired into this hot path, so certifications/ESG data is duplicated here
# rather than silently defaulting to empty and making required_certifications
# / min_renewable_energy_pct policy checks unwinnable by construction.
AGENT_CARDS = {
    VendorId.AWS: AgentCard(
        vendor_id=VendorId.AWS,
        name="AWS Vendor Agent",
        endpoint=VENDOR_ENDPOINTS[VendorId.AWS],
        capabilities=["negotiate"],
        certifications=["SOC2", "ISO27001"],
        renewable_energy_pct=100.0,
    ),
    VendorId.AZURE: AgentCard(
        vendor_id=VendorId.AZURE,
        name="Azure Vendor Agent",
        endpoint=VENDOR_ENDPOINTS[VendorId.AZURE],
        capabilities=["negotiate"],
        certifications=["SOC2", "ISO27001"],
        renewable_energy_pct=100.0,
    ),
}


class NegotiationRequest(BaseModel):
    gpu_type: str = "H100"
    gpu_count: int
    contract_months: int
    budget_ceiling_usd: float
    region: str | None = None
    raw_input: str
    blocked_vendors: list[VendorId] = []
    required_certifications: list[str] = []
    min_renewable_energy_pct: float | None = None
    initial_claimed_discounts: dict[VendorId, float]


class ApprovalRequest(BaseModel):
    approved_by: str


def _pricing_source():
    return runtime_factories.pricing_source()


def _narrator():
    return runtime_factories.narrator()


def _plausibility_screener():
    return runtime_factories.plausibility_screener()


def _execution_mode() -> str:
    """`in_process` unless `PACT_DISTRIBUTED=true` AND Pub/Sub/Firestore
    are actually reachable right now -- a flag alone is never trusted, the
    same discipline `_plausibility_screener()` already applies to Ollama.
    Unlike that best-effort fallback, this one logs loudly on downgrade:
    silently dropping a mode someone explicitly asked for (possibly mid-
    demo) would itself be an undisclosed-behavior problem."""
    if os.environ.get("PACT_DISTRIBUTED", "").lower() != "true":
        return "in_process"
    if not (pubsub_client.is_configured() and negotiation_store.is_configured()):
        logger.warning("PACT_DISTRIBUTED=true but Pub/Sub/Firestore are unreachable; falling back to in_process")
        return "in_process"
    return "distributed"


def _store():
    if _execution_mode() == "distributed":
        return FirestoreStore()
    return _in_process_store


def _poll_store_until_terminal(store, negotiation_id: str, timeout: float = 18.0, interval: float = 0.25):
    """Bounded poll for the distributed path -- keeps `POST /negotiations`
    synchronous for the frontend's existing contract in the normal
    (sub-second) case. `HttpVendorClient` already uses a 35s timeout for
    the same class of reason (real-world pricing-API latency, caught via
    a real CI run) -- 18s here comfortably covers that. A timeout returns
    the still-`IN_PROGRESS` state -- an existing, valid status, an honest
    outcome rather than a failure -- and `GET /negotiations/{id}` remains
    the way to keep checking."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = store.load(negotiation_id)
        if state is not None and state.status != NegotiationStatus.IN_PROGRESS:
            return state
        time.sleep(interval)
    return store.load(negotiation_id)


@router.post("", response_model=NegotiationState, dependencies=[Depends(require_bearer_token)])
@limiter.limit("20/minute")
def create_negotiation(request: Request, req: NegotiationRequest, background_tasks: BackgroundTasks) -> NegotiationState:
    requirement = Requirement(
        gpu_type=req.gpu_type,
        gpu_count=req.gpu_count,
        contract_months=req.contract_months,
        budget_ceiling_usd=req.budget_ceiling_usd,
        region=req.region,
        raw_input=req.raw_input,
    )
    policy = PolicyConstraints(
        budget_ceiling_usd=req.budget_ceiling_usd,
        blocked_vendors=req.blocked_vendors,
        required_certifications=req.required_certifications,
        min_renewable_energy_pct=req.min_renewable_energy_pct,
    )
    candidate_vendors = list(req.initial_claimed_discounts.keys())
    store = _store()

    if _execution_mode() == "distributed":
        negotiation_id = str(uuid.uuid4())
        initial_state = NegotiationState(negotiation_id=negotiation_id, requirement=requirement, policy=policy)
        initial_state.log(EventType.REQUIREMENT_RECEIVED, detail=requirement.raw_input)
        store.save(initial_state)

        pubsub_client.publish_negotiation_requested(
            negotiation_id,
            {
                "gpu_type": req.gpu_type,
                "gpu_count": req.gpu_count,
                "contract_months": req.contract_months,
                "budget_ceiling_usd": req.budget_ceiling_usd,
                "region": req.region,
                "raw_input": req.raw_input,
                "blocked_vendors": [v.value for v in req.blocked_vendors],
                "required_certifications": req.required_certifications,
                "min_renewable_energy_pct": req.min_renewable_energy_pct,
                "initial_claimed_discounts": {v.value: rate for v, rate in req.initial_claimed_discounts.items()},
            },
        )
        state = _poll_store_until_terminal(store, negotiation_id)
    else:
        state = run_negotiation(
            requirement=requirement,
            policy=policy,
            candidate_vendors=candidate_vendors,
            agent_cards={v: AGENT_CARDS[v] for v in candidate_vendors},
            pricing_source=_pricing_source(),
            initial_claimed_discounts=req.initial_claimed_discounts,
            vendor_client=HttpVendorClient(VENDOR_ENDPOINTS),
            narrator=_narrator(),
            plausibility_screener=_plausibility_screener(),
        )
        store.save(state)

    # BigQuery load jobs take real seconds -- never hold the API response on
    # them (PRD §27's discipline applied to latency, not just correctness).
    # Always triggered here, in the API layer, never inside the worker's
    # message handler -- Pub/Sub's at-least-once redelivery would otherwise
    # produce duplicate rows on a redelivered message.
    background_tasks.add_task(bigquery_sink.write_negotiation, state)
    return state


@router.get("/{negotiation_id}", response_model=NegotiationState)
def get_negotiation(negotiation_id: str) -> NegotiationState:
    state = _store().load(negotiation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return state


@router.get("/{negotiation_id}/evidence")
def get_negotiation_evidence(negotiation_id: str) -> dict:
    """The exact canonical bundle `evidence_hash` was computed over, plus
    the hash itself -- self-verifying: recompute SHA-256 over
    `json.dumps(bundle, sort_keys=True, separators=(",", ":"))` and it
    matches `evidence_hash` below, or it doesn't (see
    `pact/security/evidence_hash.py` and
    `tests/unit/test_evidence_hash.py`).

    `audit_chain_head` is a different, complementary proof: the last
    event's `chain_hash`, which itself depends on every earlier event's
    real timestamp and content (see `pact/security/audit_chain.py`).
    Recomputing it from `events` with `recompute_chain()` and comparing
    against each event's own `chain_hash` proves the logged sequence
    wasn't reordered, edited, or has anything missing -- a property the
    single whole-bundle `evidence_hash` doesn't individually prove."""
    state = _store().load(negotiation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return {
        "negotiation_id": state.negotiation_id,
        "evidence_hash": state.evidence_hash,
        "audit_chain_head": state.events[-1].chain_hash if state.events else None,
        "bundle": evidence_bundle(state),
    }


@router.post("/{negotiation_id}/approve", response_model=NegotiationState, dependencies=[Depends(require_bearer_token)])
@limiter.limit("20/minute")
def approve_negotiation(
    request: Request, negotiation_id: str, req: ApprovalRequest, background_tasks: BackgroundTasks
) -> NegotiationState:
    store = _store()
    state = store.load(negotiation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    if state.status != NegotiationStatus.AGREED_PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Cannot approve a negotiation in status {state.status.value}")
    approval.approve(state, approved_by=req.approved_by)
    store.save(state)
    background_tasks.add_task(bigquery_sink.write_negotiation, state)  # re-sync: records the approval too
    return state


@router.get("", response_model=list[NegotiationState])
def list_negotiations() -> list[NegotiationState]:
    return _store().list_all()
