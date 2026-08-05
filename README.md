# Pact

Autonomous B2B procurement negotiation. A Buyer Agent negotiates
simultaneously with independent Vendor Agents over real HTTP, verifies
every vendor claim against real, live pricing data, enforces policy as a
hard gate, and produces an evidence-backed decision for human approval —
nothing is fabricated, and nothing is finalized without an explicit
approval action.

Full product and architecture documentation: [`docs/PRD.md`](docs/PRD.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

```
docs/                   PRD and architecture documentation
backend/
  pact/                 Core package: 6-agent pipeline, orchestration, API
    agents/             Buyer, Discovery, Negotiation, Verification, Compliance, Decision
    negotiation/         Deterministic concession-curve logic (no LLM in the price path)
    orchestration/        The pipeline (graph.py), state/event log, human approval gate
    mcp_tools/            pricing_lookup / verify_claim tool wrappers
    a2a/                  HTTP-based vendor transport (see note below)
    models/               Shared data schemas
    api/                  FastAPI routes (pact-core)
    main.py               pact-core entrypoint
  vendors/
    aws_vendor/            Real AWS Price List Bulk API integration
    azure_vendor/           Real, live Azure Retail Prices API integration
    gcp_vendor/, runpod_vendor/   Scaffolded, not yet wired to a real API
  eval/                   Scenario catalogue (PRD §18) + real aggregate results
  scripts/                run_scenario.py (single run), run_catalogue.py (evaluation harness)
  tests/                  unit / integration / e2e / failure_path
frontend/                 Vite + React + TypeScript UI (Decision view, Replay timeline)
infra/                    Deployment configs (Cloud Run, BigQuery) — not yet populated
```

## Prerequisites

- Python 3.11+
- Node 18+
- [Ollama](https://ollama.com) (for self-hosted Gemma) — optional for the current build; Gemma isn't wired into the running pipeline yet (see Current Status below)

## Setup

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

### Gemini (optional but recommended)

```bash
cd backend
cp .env.example .env
# edit .env, set GEMINI_API_KEY to a real key from https://aistudio.google.com
```

Without a key, the Decision Agent still produces a correct, evidence-backed
reasoning statement from a deterministic template — Gemini only narrates
the same facts in richer natural language (PRD §16), and its role is
strictly narration, never determining a price, a verification verdict, or
a compliance verdict. If the Gemini call fails or times out for any
reason, the system falls back to the deterministic template automatically
and logs a `narration_degraded` event rather than blocking the decision
(PRD §27).

## Running it

Three backend services, then the frontend — four terminals, or run each with `&`:

```bash
cd backend && source .venv/bin/activate
uvicorn vendors.aws_vendor.app:app --port 9001    # AWS vendor (real AWS Price List Bulk API)
uvicorn vendors.azure_vendor.app:app --port 9002   # Azure vendor (real Azure Retail Prices API)
uvicorn pact.main:app --port 8000                  # pact-core API

cd frontend
npm run dev   # http://localhost:5173
```

Open `http://localhost:5173`. The form is pre-filled with the PRD's
Flagship Demonstration Scenario (8× H100, 3-month contract, $115,000
budget). Click **Start negotiation** to run it live against the real AWS
and Azure vendor services.

### Or drive the API directly

```bash
curl -X POST http://localhost:8000/negotiations \
  -H "Content-Type: application/json" \
  -d '{
    "gpu_count": 8, "contract_months": 3, "budget_ceiling_usd": 115000,
    "raw_input": "Need 8 H100 GPUs, 3-month contract, $115,000 budget",
    "initial_claimed_discounts": {"aws": 0.25, "azure": 0.8152}
  }'
```

### Or run one scenario from the CLI, without any servers

```bash
cd backend && source .venv/bin/activate
python scripts/run_scenario.py --fixture flagship --approve
```

## Tests

```bash
cd backend && source .venv/bin/activate
pytest tests/            # unit + integration (hits real AWS/Azure APIs) + e2e
```

Integration tests that spawn the vendor services as real subprocesses
(`test_vendor_client_live.py`, `test_flagship_scenario_live.py`,
`test_api.py`) take a few seconds longer than the rest — they're proving
the system negotiates over genuine HTTP between separate processes, not
asserting against in-process function calls.

## Evaluation harness

```bash
cd backend && source .venv/bin/activate
python scripts/run_catalogue.py
```

Runs every scenario in `eval/scenario_catalogue.yaml` through the exact
same pipeline code path as a live negotiation, prints a results table,
writes real (not invented) aggregate statistics — agreement rate, average
rounds-to-agreement, average savings, claim/compliance catch rates — to
`eval/results.json`, and sinks every run to the same BigQuery tables the
live API writes to. Run the real SQL aggregate query against actual
logged data with:

```bash
bq query --project_id=pact-hackathon --use_legacy_sql=false < ../infra/bigquery/queries_aggregate.sql
```

## Current status / honest scope

This build implements the PRD's Flagship Demonstration Scenario and the
full negotiation pipeline end to end, verified against real external
data. What's real right now:

- Deterministic negotiation core, all 6 agents, both feedback loops
- Real AWS pricing (Price List Bulk API) and real Azure pricing (Retail
  Prices API, including real spot pricing) — no mocks, no fixtures, in
  the live path
- Genuinely separate vendor services negotiating over real HTTP
- The human approval gate (nothing finalizes without it)
- The evaluation harness, computing real statistics from real runs
- **Gemini** — real narration of the Decision Agent's reasoning
  (`pact/models/gemini_client.py`), strictly isolated from the
  price-decision path; bounded to a 10s timeout with one retry, and
  degrades to a deterministic template (logged as `narration_degraded`,
  never silent) if the call fails — verified working both ways against
  the live API, including under a real transient Gemini outage during
  development
- **Gemma** — real, self-hosted (local Ollama) plausibility pre-screen on
  every vendor claim (`pact/models/gemma_client.py`), logged as its own
  `plausibility_screened` event -- explicitly independent of, and never
  authoritative over, the deterministic verification verdict that
  actually gates the negotiation (FR-4's reproducibility guarantee is
  preserved: an LLM never decides match/mismatch)
- **BigQuery** — real project (`pact-hackathon`), real dataset/tables
  (`infra/bigquery/schema.sql`), written via batch load jobs (the
  no-billing-account-required path — streaming inserts need billing
  enabled, load jobs don't). Both the live API and the evaluation harness
  write to the same tables; `infra/bigquery/queries_aggregate.sql` computes
  real aggregate statistics via SQL against actual logged runs. API writes
  run as a FastAPI background task so a slow load job never holds up the
  HTTP response.

Not yet wired into the running system (see `docs/PRD.md` §11's Google
Technology Stack table for the intended role of each):

- **Gemini — requirement parsing and per-move narration** — the Reasoning
  narration above is live; parsing free-text/voice/photo input (FR-1) and
  narrating individual negotiation moves are designed but not yet
  connected. Typed structured input (what the form/API accept today) is
  still honest, non-fabricated input — just a narrower slice of FR-1 than
  the full modality set.
- **GCP vendor**, **RunPod vendor** — scaffolded, no real pricing
  integration yet
- **Google ADK** — the 6 agents are structured as ADK would orchestrate
  them, but the current pipeline (`orchestration/graph.py`) is a direct
  Python implementation, not literally running through ADK

Nothing in this list is faked to appear more complete than it is — see
`docs/PRD.md` §32 for the project's explicit non-claims.

## Deployment

**Cloud Run was not used.** It requires a linked billing account (even
though actual usage would very likely stay within the free tier) — this
build deliberately avoids requiring payment info anywhere, including
here.

Instead: `infra/huggingface/Dockerfile` builds a single container running
all three backend services plus the built frontend behind one port
(7860), tested and confirmed working locally. Hugging Face Spaces was
evaluated as a free host for that container next, but its Docker SDK
turned out to require a paid PRO subscription on their current pricing —
also ruled out for the same no-payment reason.

The container is instead exposed via **ngrok** (free account + authtoken,
no card) for a real, working public URL:

```bash
docker build -f infra/huggingface/Dockerfile -t pact-deploy .
docker run -d --name pact-deploy-run -p 7860:7860 -e GEMINI_API_KEY="<key>" pact-deploy
ngrok http 7860
```

This is a real, live, working deployment — verified end to end (health
check, frontend, and a full negotiation with correct results) over the
actual public internet, not just localhost. Two honest caveats: it runs
on the operator's own machine rather than a managed cloud host (the
container must stay running for the URL to work), and ngrok's free tier
issues a new random subdomain each time the tunnel restarts, and shows
first-time visitors a one-click interstitial page before reaching the
app. Both are disclosed limitations of the no-payment path chosen here,
not attempts to hide them.
