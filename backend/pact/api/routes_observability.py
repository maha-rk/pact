"""Real observability dashboard endpoint: live model-call and
negotiation-aggregate statistics computed via real SQL against BigQuery
-- the same real records (PRD §25's "one real record, queried two ways"),
queried a third way. Closes the architecture review's "OpenTelemetry
traces reach BigQuery but nothing visualizes them" gap.

Read-only, not gated behind auth (matches `GET /negotiations`), and never
raises into a 500 if BigQuery is unreachable -- a dashboard that fails to
load must not look like a broken negotiation pipeline (PRD §27's
discipline applied here too)."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("pact.routes_observability")

router = APIRouter(prefix="/observability", tags=["observability"])

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "pact-hackathon")
DATASET_ID = "pact"

_client = None


def _get_client():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=PROJECT_ID)
    return _client


class ModelTraceSummaryRow(BaseModel):
    model: str | None
    call_count: int
    avg_latency_ms: float | None
    total_tokens: int | None
    error_rate: float | None


class NegotiationAggregateSummary(BaseModel):
    total_runs: int
    agreement_rate: float | None
    avg_rounds_to_agreement: float | None
    avg_savings_pct: float | None
    claim_mismatch_catch_rate: float | None
    compliance_rejection_rate: float | None


class ObservabilitySummary(BaseModel):
    available: bool
    error: str | None = None
    model_traces: list[ModelTraceSummaryRow] = []
    negotiations: NegotiationAggregateSummary | None = None


_MODEL_TRACE_SUMMARY_SQL = f"""
SELECT
  model,
  COUNT(*) AS call_count,
  ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
  SUM(tokens_total) AS total_tokens,
  ROUND(SAFE_DIVIDE(COUNTIF(error), COUNT(*)), 4) AS error_rate
FROM `{PROJECT_ID}.{DATASET_ID}.model_traces`
-- Belt-and-suspenders alongside the exporter-side filter in
-- observability/tracing.py: this table is documented as one row per real
-- Gemini/Gemma call, never a raw ADK/MCP auto-instrumentation span (no
-- `model` attribute) or a non-production trace. Keeps the dashboard --
-- the thing meant to prove Pact's "zero fabricated numbers" claim --
-- honest even if a future code path regresses the exporter-side filter.
WHERE model IS NOT NULL AND model != 'fake-model'
GROUP BY model
ORDER BY call_count DESC
"""

# Mirrors infra/bigquery/queries_aggregate.sql exactly (PRD §29) --
# embedded here rather than read from that file at request time, since a
# repo-relative infra/ path isn't guaranteed to exist in every deployment
# layout. Keep both in sync if either changes. Both subqueries are
# constrained to negotiation_ids present in `runs`: negotiation_events
# accumulates across every test/dev run over the project's lifetime, so
# without that constraint these rates are computed against a much larger,
# unrelated event population than `runs` and can exceed 100% (caught for
# real during this build: 116 distinct event negotiation_ids vs. 5 real
# `negotiations` rows produced an impossible 1966% figure before the fix).
_NEGOTIATION_AGGREGATE_SQL = f"""
WITH runs AS (
  SELECT negotiation_id, status, final_price_usd, savings_pct, approved
  FROM `{PROJECT_ID}.{DATASET_ID}.negotiations`
  -- Evaluation-harness runs only (PRD §29). Ad-hoc demo/API runs are
  -- overwhelmingly the flagship happy path, so pooling them drives the
  -- agreement rate upward toward 100% with every demo click -- measuring
  -- how often the button was pressed, not how the system behaves. The
  -- catalogue is a designed sample that deliberately includes no-deal
  -- outcomes (impossible budget, blocked vendor, unmet certification),
  -- so its proportions stay stable however many times it is re-run.
  WHERE scenario_id IS NOT NULL
),
per_negotiation_rounds AS (
  SELECT negotiation_id, MAX(round_number) AS rounds_to_agreement
  FROM `{PROJECT_ID}.{DATASET_ID}.negotiation_events`
  WHERE event_type = 'offer_made' AND negotiation_id IN (SELECT negotiation_id FROM runs)
  GROUP BY negotiation_id
),
claim_catches AS (
  SELECT DISTINCT negotiation_id
  FROM `{PROJECT_ID}.{DATASET_ID}.negotiation_events`
  WHERE event_type = 'claim_rejected' AND negotiation_id IN (SELECT negotiation_id FROM runs)
),
compliance_catches AS (
  SELECT DISTINCT negotiation_id
  FROM `{PROJECT_ID}.{DATASET_ID}.negotiation_events`
  WHERE event_type = 'compliance_rejected' AND negotiation_id IN (SELECT negotiation_id FROM runs)
)
SELECT
  COUNT(*) AS total_runs,
  ROUND(SAFE_DIVIDE(COUNTIF(r.status = 'finalized' OR r.status = 'agreed_pending_approval'), COUNT(*)), 4) AS agreement_rate,
  ROUND(AVG(pr.rounds_to_agreement), 2) AS avg_rounds_to_agreement,
  ROUND(AVG(r.savings_pct), 4) AS avg_savings_pct,
  ROUND(SAFE_DIVIDE((SELECT COUNT(*) FROM claim_catches), COUNT(*)), 4) AS claim_mismatch_catch_rate,
  ROUND(SAFE_DIVIDE((SELECT COUNT(*) FROM compliance_catches), COUNT(*)), 4) AS compliance_rejection_rate
FROM runs r
LEFT JOIN per_negotiation_rounds pr USING (negotiation_id)
"""


@router.get("/summary", response_model=ObservabilitySummary)
def get_observability_summary() -> ObservabilitySummary:
    try:
        client = _get_client()
        model_rows = [ModelTraceSummaryRow(**dict(row)) for row in client.query(_MODEL_TRACE_SUMMARY_SQL).result()]
        agg_rows = list(client.query(_NEGOTIATION_AGGREGATE_SQL).result())
        negotiations = NegotiationAggregateSummary(**dict(agg_rows[0])) if agg_rows else None
        return ObservabilitySummary(available=True, model_traces=model_rows, negotiations=negotiations)
    except Exception as exc:
        logger.warning("Observability summary query failed: %s", exc)
        return ObservabilitySummary(available=False, error=str(exc))
