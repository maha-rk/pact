"""BigQuery sink for negotiation logs (PRD §25, FR-9). The authoritative
store: the same table backs both the replay UI (FR-10) and the evaluation
harness's aggregate statistics (§29) -- one real record, queried two ways.

If BigQuery is unavailable or unconfigured, writes are skipped with a
warning rather than raising -- persistence failures must never block a
negotiation from completing or being approved (PRD §27's discipline
applied to this dependency too).
"""

from __future__ import annotations

import logging
import os

from pact.orchestration.state import NegotiationState
from pact.security import field_encryption

logger = logging.getLogger("pact.bigquery_sink")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "pact-hackathon")
DATASET_ID = "pact"

_client = None


def _get_client():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=PROJECT_ID)
    return _client


def is_configured() -> bool:
    try:
        _get_client()
        return True
    except Exception:
        return False


def _maybe_encrypted(value) -> str | None:
    """Real AES-256-GCM encryption (`pact/security/field_encryption.py`)
    for BigQuery-bound fields that are sensitive in this schema: the
    buyer's true budget ceiling (this system's closest analog to a
    reservation price/BATNA), the final negotiated price, and the
    Decision Agent's reasoning text. Falls back to plaintext (stringified,
    since the column is STRING either way) with a loud warning if
    `PACT_FIELD_ENCRYPTION_KEY` isn't configured -- disclosed, not silent,
    same posture as `AUTH_REQUIRED` and `PACT_DISTRIBUTED` (PRD §26)."""
    if value is None:
        return None
    text = str(value)
    if field_encryption.is_configured():
        return field_encryption.encrypt_field(text)
    logger.warning(
        "PACT_FIELD_ENCRYPTION_KEY not set -- writing this BigQuery field as plaintext "
        "(real data, just not application-level encrypted; see PRD §26)."
    )
    return text


def write_negotiation(state: NegotiationState, scenario_id: str | None = None) -> None:
    """Writes one row to `negotiations` and one row per event to
    `negotiation_events`. Best-effort: logs and returns on failure.

    `scenario_id` is set only by the evaluation harness
    (`scripts/run_catalogue.py`) and stays `None` for live API and
    ad-hoc demo runs -- see `infra/bigquery/schema.sql` for why that
    distinction is load-bearing for honest aggregate statistics."""
    try:
        client = _get_client()
        decision = state.decision

        savings_pct = None
        if decision and decision.final_price_usd is not None and state.offers:
            vendor_offers = [o for o in state.offers if o.vendor_id == decision.selected_vendor]
            if vendor_offers:
                opening = vendor_offers[0].price_usd
                if opening:
                    savings_pct = (opening - decision.final_price_usd) / opening

        negotiation_row = {
            "negotiation_id": state.negotiation_id,
            "created_at": state.events[0].timestamp.isoformat() if state.events else None,
            "gpu_type": state.requirement.gpu_type,
            "gpu_count": state.requirement.gpu_count,
            "contract_months": state.requirement.contract_months,
            "budget_ceiling_usd": _maybe_encrypted(state.requirement.budget_ceiling_usd),
            "status": state.status.value,
            "selected_vendor": decision.selected_vendor.value if decision and decision.selected_vendor else None,
            "final_price_usd": _maybe_encrypted(decision.final_price_usd if decision else None),
            "savings_pct": savings_pct,
            "reasoning": _maybe_encrypted(decision.reasoning if decision else None),
            "approved": decision.approved if decision else False,
            "approved_at": decision.approved_at.isoformat() if decision and decision.approved_at else None,
            "scenario_id": scenario_id,
        }
        _load_rows(client, f"{PROJECT_ID}.{DATASET_ID}.negotiations", [negotiation_row])

        # `detail` is real free-text audit content (can embed dollar
        # figures and reasoning, e.g. "$118,886.40 exceeds the budget
        # ceiling of $115,000.00") -- encrypted for the same reason
        # budget_ceiling_usd/final_price_usd/reasoning are (PRD §26).
        # `event_type`, `vendor_id`, `round_number` stay plaintext: the
        # evaluation harness's aggregate SQL (§29) filters on event_type,
        # and losing that would break real, working statistics for a
        # field that's inherently not free text.
        event_rows = [
            {
                "negotiation_id": state.negotiation_id,
                "event_type": e.event_type.value,
                "vendor_id": e.vendor_id.value if e.vendor_id else None,
                "round_number": e.round_number,
                "detail": _maybe_encrypted(e.detail),
                "timestamp": e.timestamp.isoformat(),
            }
            for e in state.events
        ]
        if event_rows:
            _load_rows(client, f"{PROJECT_ID}.{DATASET_ID}.negotiation_events", event_rows)
    except Exception as exc:
        logger.warning("BigQuery write skipped (negotiation %s): %s", state.negotiation_id, exc)


def _load_rows(client, table_id: str, rows: list[dict]) -> None:
    """Batch load job -- unlike streaming inserts, this works on a
    no-billing / sandbox-mode project (PRD's cardless setup constraint)."""
    from google.cloud import bigquery

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    job = client.load_table_from_json(rows, table_id, job_config=job_config)
    job.result()  # block until the load job completes; raises on failure
