# Pact

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Node](https://img.shields.io/badge/node-18%2B-339933)
![Tests](https://img.shields.io/badge/tests-44-brightgreen)
![Built for](https://img.shields.io/badge/Built%20for-AI%20Agent%20Builder%20Series%202026-8A2BE2)

**Pact is a trustworthy autonomous procurement system where organizational
agents negotiate directly with other organizational agents, every claim is
independently verified, every decision is auditable, and every
recommendation is grounded in real evidence rather than a fabricated
score.**

A Buyer Agent negotiates simultaneously with independent Vendor Agents
over real HTTP, verifies every vendor claim against real, live pricing
data, enforces policy as a hard gate, and produces an evidence-backed
decision — nothing is fabricated, and nothing is finalized without
explicit human approval.

Full product and architecture documentation: [`docs/PRD.md`](docs/PRD.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Why this exists

Procurement teams with recurring vendor spend already run this process —
manually. A human reads vendor quotes, tries to negotiate against several
suppliers at once (in practice, rarely at the same time), and has no
practical way to check whether a vendor's "discount" claim is real before
signing. Tools like SAP Ariba and Coupa digitize the paperwork around that
decision; a person still reads it and makes the call.

Pact moves the negotiation and claim-verification steps themselves into
an autonomous system — a human is retained only at the final approval
boundary, not at every step in between. In its flagship scenario (8×
H100 GPUs, 3-month contract, $115,000 budget), Pact negotiated with AWS
and Azure simultaneously over real HTTP, caught AWS's claimed discount as
fabricated against AWS's own real pricing data, rejected AWS's corrected
offer anyway for exceeding budget, and closed a real, verified, compliant
deal with Azure at **$39,246.20 — roughly 66% under the budget ceiling** —
with every one of those numbers traceable to a live public pricing API,
not invented. See [Evidence](#evidence-the-flagship-scenario) below.

## Screenshots

<!-- TODO: add screenshots before submission -->
<!-- Decision / Evidence / Reasoning view: ![Decision view](docs/screenshots/decision-view.png) -->
<!-- Negotiation Replay timeline: ![Replay timeline](docs/screenshots/replay-timeline.png) -->

## What makes Pact different

1. **Agents negotiate with agents, over a real transport.** The Buyer
   Agent and each Vendor Agent are genuinely separate HTTP services, not
   one application pretending to be several.
2. **Vendor claims are never trusted at face value.** Every claim is
   independently checked against a real, live external source before it
   can affect the outcome — a mismatch triggers renegotiation, not a
   silently accepted number.
3. **Policy can override price.** Even the cheapest verified offer is
   rejected if it violates an explicit constraint (budget, blocked
   vendor, missing certification), forcing renegotiation.
4. **Every recommendation carries evidence, never a bare score.** The
   final output is always Decision + Evidence + Reasoning, with each
   evidence item traceable to a real source.
5. **Pact measures itself with real numbers.** The evaluation harness
   runs a real scenario catalogue through the same pipeline as a live
   negotiation and computes real aggregate statistics via SQL — no
   claimed savings figure that isn't backed by a logged, re-runnable run.

## How it works

```mermaid
flowchart LR
    USER["User<br/>typed, photo, or voice input"] --> CORE["Pact Core<br/>6-agent pipeline<br/>orchestrated via Google ADK"]
    CORE <-->|real HTTP negotiation| AWS["AWS Vendor Agent<br/>real AWS Price List API"]
    CORE <-->|real HTTP negotiation| AZURE["Azure Vendor Agent<br/>real Azure Retail Prices API"]
    CORE -.->|scaffolded, not yet live| OTHER["GCP / RunPod<br/>Vendor Agents"]
    CORE --> DECISION["Decision + Evidence + Reasoning<br/>held for human approval"]
```

The six agents (Buyer, Discovery, Negotiation, Verification, Compliance,
Decision) and the full request/response sequence, including both
feedback loops, are diagrammed in detail in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The sequence below is the
flagship scenario specifically, with only the two vendors that are
genuinely wired to live pricing data today:

```mermaid
sequenceDiagram
    participant U as User
    participant N as Negotiation Agent
    participant AWS as AWS Vendor Agent
    participant AZ as Azure Vendor Agent
    participant V as Verification Agent
    participant C as Compliance Agent
    participant D as Decision Agent

    U->>N: 8x H100 GPUs, 3-month contract, $115,000 budget

    par Simultaneous negotiation over real HTTP
        N->>AWS: opening offer
        AWS-->>N: counter-offer, claims 25% committed-use discount
    and
        N->>AZ: opening offer
        AZ-->>N: counter-offer, claims 81.52% spot discount
    end

    N->>V: verify AWS's claimed discount against real AWS pricing data
    V-->>N: no such discount tier exists under 12 months — claim rejected
    N->>AWS: challenge, renegotiate
    AWS-->>N: corrected offer at the real, undiscounted rate

    N->>V: verify Azure's claimed discount against real Azure pricing data
    V-->>N: matches real, live Spot pricing — verified

    N->>C: check both verified offers against budget policy
    C-->>N: AWS's corrected offer exceeds the $115,000 ceiling — rejected
    C-->>N: Azure's offer is compliant

    N->>D: Azure selected — verified, compliant, lowest real price
    D-->>U: Decision + Evidence + Reasoning, pending approval
```

## Evidence: the flagship scenario

Every figure below is fetched live from a public pricing API or computed
directly from it — reproduce it yourself with
`python scripts/run_scenario.py --fixture flagship --approve` (see
[Running it](#running-it)).

**Claim verification**

| Vendor | Claimed | Checked against | Real value | Verdict |
|---|---|---|---|---|
| AWS | 25% committed-use discount, 3-month term | AWS Price List Bulk API | 0% — AWS's real Reserved Instance terms are 1-year and 3-year only; no 3-month tier exists | ❌ Rejected, renegotiated |
| Azure | 81.52% discount via Spot pricing | Azure Retail Prices API (live) | 81.52% — real, immediately-available Spot pricing, no minimum commitment | ✅ Verified |

**Final decision**

| | AWS (corrected) | Azure (selected) |
|---|---|---|
| Real 3-month price | $118,886.40 | $39,246.20 |
| Verified against real data | ✅ | ✅ |
| Within $115,000 budget | ❌ | ✅ |
| Outcome | Rejected on compliance grounds | Selected, pending human approval |

## Contents

- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running it](#running-it)
- [Tests](#tests)
- [Evaluation harness](#evaluation-harness)
- [Current status / honest scope](#current-status--honest-scope)
- [Deployment](#deployment)
- [License](#license)

## Repository layout

```
docs/                   PRD and architecture documentation
backend/
  pact/                 Core package: 6-agent pipeline, orchestration, API
    agents/             Buyer, Discovery, Negotiation, Verification, Compliance, Decision
    negotiation/         Deterministic concession-curve logic (no LLM in the price path)
    orchestration/        The pipeline (graph.py), state/event log, human approval gate
    mcp_tools/            pricing_lookup / verify_claim: core logic + a real MCP server exposing both as MCP tools
    adk/                   Real Google ADK orchestration of the pipeline (SequentialAgent + Runner)
    a2a/                  HTTP-based vendor transport (see note below)
    models/               Shared data schemas + Gemini Vision requirement parser
    api/                  FastAPI routes (pact-core)
    main.py               pact-core entrypoint
  vendors/
    aws_vendor/            Real AWS Price List Bulk API integration
    azure_vendor/           Real, live Azure Retail Prices API integration
    gcp_vendor/, runpod_vendor/   Scaffolded, not yet wired to a real API
  eval/                   Scenario catalogue (PRD §18) + real aggregate results
  scripts/                run_scenario.py (single run), run_catalogue.py (evaluation harness)
  tests/                  unit / integration / e2e (failure_path/ is scaffolded, no tests written yet)
frontend/                 Vite + React + TypeScript UI (Decision view, Replay timeline)
infra/                    bigquery/ (schema + aggregate query), huggingface/ (deployment container)
```

## Prerequisites

- Python 3.11+
- Node 18+
- [Ollama](https://ollama.com) running the `gemma3:4b` model — optional; without it, verification still runs correctly (the deterministic check is authoritative either way), it just skips the extra Gemma plausibility pre-screen (see [Current status](#current-status--honest-scope))

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
(PRD §27). The same key also powers the photo/voice requirement intake
(FR-1) described below.

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

Instead of the pre-filled form, you can also populate it from a photo of
a quote/invoice (**📷 Upload a photo of a quote/invoice**) or by speaking
the requirement out loud (**🎙️ Speak your requirement**, Chrome/Edge
only) — both call real Gemini Vision to extract fields (FR-1; requires
`GEMINI_API_KEY`) and pre-fill the form for you to review before starting
a negotiation.

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

### Or run the real MCP server standalone

```bash
cd backend && source .venv/bin/activate
python -m pact.mcp_tools.server   # speaks real MCP over stdio; connect any MCP client
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

<details>
<summary>Full breakdown of what's genuinely live versus not (click to expand)</summary>

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
  `plausibility_screened` event — explicitly independent of, and never
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
- **MCP** — `pact/mcp_tools/server.py` is a real MCP server (the official
  `mcp` SDK, v2.0+), exposing `pricing_lookup` and `verify_claim` as
  genuine MCP tools over the real stdio protocol, backed by the same real
  AWS/Azure pricing clients the live negotiation pipeline uses — not just
  a Protocol-shaped module named after the concept. Proven with a real
  client integration test (`tests/integration/test_mcp_server.py`) that
  spawns the server as an actual subprocess, calls `list_tools()` /
  `call_tool()` over the wire via the official client SDK, and asserts on
  real AWS pricing and the real flagship claim-mismatch — no in-process
  shortcuts. `pact/mcp_tools/pricing_tool.py` and `verification_tool.py`
  remain the plain-Python core logic these MCP tools wrap; the pipeline
  itself still calls that core logic directly (in-process, for latency),
  while the MCP server exposes the same logic to any external MCP client.
- **Google ADK** — `pact/adk/pipeline.py` runs the negotiation pipeline
  through a real ADK `SequentialAgent` under a real ADK `Runner` and
  `InMemorySessionService`, composed of two genuinely separate ADK
  agents (Discovery, then Negotiation/Verification/Compliance/Decision —
  the natural phase boundary, since verification and compliance are
  checked per-offer inside each live negotiation round, not as
  independently-scheduled steps). Both ADK agents call the exact same
  phase functions `orchestration/graph.py`'s direct path calls — one
  source of truth for the negotiation logic, proven identical via
  `tests/e2e/test_flagship_scenario_via_adk.py`, which runs the flagship
  scenario through the real ADK agent tree and asserts the same verified
  numbers as the direct path, plus that the two ADK agents genuinely ran
  in order. `orchestration/graph.run_negotiation` remains what the live
  API, CLI, and every other test call directly.
- **Gemini Vision — photo/voice requirement intake (FR-1)** —
  `pact/models/requirement_parser.py` calls real Gemini Vision (structured
  JSON output via `response_json_schema`) to extract `gpu_count`,
  `contract_months`, `budget_ceiling_usd`, `gpu_type`, and `region` from
  either a photographed quote/invoice or a text transcript, exposed via
  `POST /requirements/parse-image` and `POST /requirements/parse-text`.
  The model is explicitly instructed to return `null` for any field not
  actually present in the input rather than guess — verified against the
  real API with a rendered synthetic invoice image (correctly extracted
  8 GPUs / 3 months / $115,000) and against ambiguous text (correctly
  returned all-null when nothing concrete was stated), in
  `tests/integration/test_requirement_parser.py`. The frontend's "Upload a
  photo" button sends an image straight to the image endpoint; "Speak your
  requirement" uses the browser's native `SpeechRecognition` API to get a
  transcript (a real, working speech-to-text conversion, not a stub), then
  sends that transcript to the text endpoint. Either way, extracted fields
  only pre-fill the existing form for the user to review — nothing is
  auto-submitted, preserving both the human-in-the-loop framing and the
  "no invented value" acceptance criterion.

Not yet wired into the running system (see `docs/PRD.md` §11's Google
Technology Stack table for the intended role of each):

- **Gemini — per-move negotiation narration** — narrating individual
  negotiation moves in real time (as opposed to the final Reasoning
  statement, which is live) is designed but not yet connected.
- **GCP vendor**, **RunPod vendor** — scaffolded, no real pricing
  integration yet

Nothing in this list is faked to appear more complete than it is — see
`docs/PRD.md` §32 for the project's explicit non-claims.

</details>

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

## License

MIT — see [LICENSE](LICENSE).
