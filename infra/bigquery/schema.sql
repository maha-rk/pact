-- BigQuery schema for Pact's negotiation log (PRD §25, FR-9).
-- Two tables, one real record queried two ways: `negotiations` gives fast
-- aggregate access (evaluation harness, §29); `negotiation_events` is the
-- full timestamped audit trail backing the replay UI (FR-10, §22).

CREATE TABLE IF NOT EXISTS `pact-hackathon.pact.negotiations` (
  negotiation_id STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  gpu_type STRING,
  gpu_count INT64,
  contract_months INT64,
  budget_ceiling_usd FLOAT64,
  status STRING,
  selected_vendor STRING,
  final_price_usd FLOAT64,
  savings_pct FLOAT64,
  reasoning STRING,
  approved BOOL,
  approved_at TIMESTAMP,
  approved_by STRING
);

CREATE TABLE IF NOT EXISTS `pact-hackathon.pact.negotiation_events` (
  negotiation_id STRING NOT NULL,
  event_type STRING NOT NULL,
  vendor_id STRING,
  round_number INT64,
  detail STRING,
  timestamp TIMESTAMP NOT NULL
);
