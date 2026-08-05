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


def write_negotiation(state: NegotiationState) -> None:
    """Writes one row to `negotiations` and one row per event to
    `negotiation_events`. Best-effort: logs and returns on failure."""
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
            "budget_ceiling_usd": state.requirement.budget_ceiling_usd,
            "status": state.status.value,
            "selected_vendor": decision.selected_vendor.value if decision and decision.selected_vendor else None,
            "final_price_usd": decision.final_price_usd if decision else None,
            "savings_pct": savings_pct,
            "reasoning": decision.reasoning if decision else None,
            "approved": decision.approved if decision else False,
            "approved_at": decision.approved_at.isoformat() if decision and decision.approved_at else None,
        }
        _load_rows(client, f"{PROJECT_ID}.{DATASET_ID}.negotiations", [negotiation_row])

        event_rows = [
            {
                "negotiation_id": state.negotiation_id,
                "event_type": e.event_type.value,
                "vendor_id": e.vendor_id.value if e.vendor_id else None,
                "round_number": e.round_number,
                "detail": e.detail,
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
