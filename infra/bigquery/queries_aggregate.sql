-- Real aggregate evaluation statistics (PRD §29), computed via SQL
-- against actually-logged negotiation runs -- never invented numbers.
-- Run: bq query --project_id=pact-hackathon --use_legacy_sql=false < this file

WITH runs AS (
  SELECT
    negotiation_id,
    status,
    final_price_usd,
    savings_pct,
    approved
  FROM `pact-hackathon.pact.negotiations`
),
per_negotiation_rounds AS (
  SELECT
    negotiation_id,
    MAX(round_number) AS rounds_to_agreement
  FROM `pact-hackathon.pact.negotiation_events`
  WHERE event_type = 'offer_made' AND negotiation_id IN (SELECT negotiation_id FROM runs)
  GROUP BY negotiation_id
),
-- Constrained to negotiation_ids that actually have a `runs` row --
-- negotiation_events accumulates across every test/dev run over the
-- project's lifetime, so without this filter these rates are computed
-- against a much larger, unrelated event population than `runs` and can
-- exceed 100% (caught for real: 116 distinct event negotiation_ids vs.
-- 5 real `negotiations` rows produced an impossible 1966% figure before
-- this fix).
claim_catches AS (
  SELECT DISTINCT negotiation_id
  FROM `pact-hackathon.pact.negotiation_events`
  WHERE event_type = 'claim_rejected' AND negotiation_id IN (SELECT negotiation_id FROM runs)
),
compliance_catches AS (
  SELECT DISTINCT negotiation_id
  FROM `pact-hackathon.pact.negotiation_events`
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
LEFT JOIN per_negotiation_rounds pr USING (negotiation_id);
