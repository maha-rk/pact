-- BigQuery schema for Pact's negotiation log (PRD §25, FR-9).
-- Two tables, one real record queried two ways: `negotiations` gives fast
-- aggregate access (evaluation harness, §29); `negotiation_events` is the
-- full timestamped audit trail backing the replay UI (FR-10, §22).

-- budget_ceiling_usd, final_price_usd, and reasoning are STRING, not
-- FLOAT64/plain text -- when PACT_FIELD_ENCRYPTION_KEY is configured
-- (pact/security/field_encryption.py), these three columns hold real
-- AES-256-GCM ciphertext (base64), not the raw value. When the key
-- isn't configured, they hold the plaintext value stringified, with a
-- warning logged at write time -- disclosed, not silent (PRD §26).
-- savings_pct stays FLOAT64 and unencrypted: it's the field the
-- evaluation harness's aggregate SQL (queries_aggregate.sql) actually
-- reads, and a ratio is materially less sensitive alone than the raw
-- dollar figures it's derived from.
CREATE TABLE IF NOT EXISTS `pact-hackathon.pact.negotiations` (
  negotiation_id STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  gpu_type STRING,
  gpu_count INT64,
  contract_months INT64,
  budget_ceiling_usd STRING,
  status STRING,
  selected_vendor STRING,
  final_price_usd STRING,
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

-- Real OpenTelemetry request-level tracing for every Gemini/Gemma call
-- (PRD §23b). One row per span: never the raw prompt, only a hash of it
-- (consistent with §23a's PII handling), plus real token usage and
-- latency read directly off the span.
CREATE TABLE IF NOT EXISTS `pact-hackathon.pact.model_traces` (
  trace_id STRING NOT NULL,
  span_id STRING NOT NULL,
  span_name STRING NOT NULL,
  negotiation_id STRING,
  model STRING,
  model_version STRING,
  prompt_hash STRING,
  prompt_length_chars INT64,
  tokens_prompt INT64,
  tokens_completion INT64,
  tokens_total INT64,
  latency_ms FLOAT64,
  error BOOL,
  error_message STRING,
  start_time TIMESTAMP NOT NULL
);
