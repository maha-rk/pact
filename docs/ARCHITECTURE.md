# Pact — Architecture

Five diagrams, each answering a different question, rather than one dense
diagram trying to answer all of them at once: a system overview (what is
this, at a glance), the agent orchestration detail (how the six agents
relate), a negotiation sequence (what actually happens, in order, during a
live run), the data/infrastructure layer (what's real, and where it
lives), and the evaluation harness pipeline (how a claim like "Pact saves
money" becomes a provable, re-runnable result).

---

## 1. System Overview

The high-level shape: what goes in, what orchestrates it, who it talks to
externally, what comes out.

```mermaid
flowchart LR
    USER["User<br/>voice or photo"] --> GUARDRAILS["Guardrails<br/>prompt-injection classifier + Presidio PII<br/>real, self-hosted — PRD §23a"]
    GUARDRAILS --> GATEWAY["API Gateway<br/>real JWT auth + rate limiting<br/>(pact-core middleware) — PRD §23a"]
    GATEWAY --> ORCH["Pact<br/>Agent Orchestration<br/>(Google ADK)"]
    ORCH <-->|A2A Protocol<br/>live negotiation| VENDORS["Independent Vendor Agents<br/>AWS · Azure · GCP · RunPod"]
    ORCH --> DECISION["Final Decision<br/>Evidence + Reasoning<br/>no fabricated scores"]
    ORCH -.->|deployed on| INFRA["Cloud Run · BigQuery · Vertex AI"]
```

**Read this as**: a user states a real requirement once. Everything else —
finding vendors, negotiating with several of them at once, verifying their
claims, enforcing policy, and deciding — happens autonomously inside Pact's
agent orchestration layer, with A2A as the actual channel Pact uses to
transact with vendors that are not part of the same system. Both Guardrails
and Gateway are real: photo intake is covered by a real transcription call
that feeds the same text-based guardrail text/voice already use; the
Gateway's JWT auth is real but off by default (`AUTH_REQUIRED=false`,
since this build has no end-user accounts to protect yet), and its rate
limiting is real and always on. Neither is a separate physical process —
both are implemented as `pact-core` middleware, a disclosed choice at this
single-operator scale (PRD §23a).

---

## 2. Multi-Agent Orchestration (inside ADK)

The six agents and how they hand off work to each other, including the two
feedback loops that make this a real negotiation rather than a fixed
pipeline.

```mermaid
flowchart TB
    BUYER["Buyer Agent<br/>parses requirements,<br/>holds negotiation strategy<br/>(reservation price, BATNA)"]
    DISCOVERY["Discovery Agent<br/>finds Vendor Agents<br/>via A2A Agent Cards"]
    NEGOTIATION["Negotiation Agent<br/>deterministic concession-curve<br/>logic drives offers"]
    COMPLIANCE["Compliance Agent<br/>enforces budget/policy,<br/>can reject a deal live"]
    VERIFICATION["Verification Agent<br/>cross-checks vendor claims<br/>against real external data"]
    DECISION["Decision Agent<br/>Evidence + Reasoning output"]

    BUYER --> DISCOVERY --> NEGOTIATION
    NEGOTIATION --> COMPLIANCE --> VERIFICATION --> DECISION
    VERIFICATION -.->|claim mismatch found,<br/>send back| NEGOTIATION
    COMPLIANCE -.->|deal rejected,<br/>renegotiate| NEGOTIATION
```

**Why two feedback loops, not a straight line**: a real negotiation isn't a
pipeline that always finishes on the first pass. If the Verification Agent
catches a vendor claim that doesn't match real external data, or the
Compliance Agent finds the current best offer violates a policy constraint,
the Negotiation Agent has to go back and negotiate again — this is what
makes the system a genuine negotiator rather than a script that runs once
and reports whatever it got.

---

## 3. Negotiation Sequence (a real run, in order)

This is what actually happens, step by step, during one live negotiation —
including the two "wow" moments: a negotiating claim that fails
verification, and a rejected deal.

```mermaid
sequenceDiagram
    participant U as User
    participant B as Buyer Agent
    participant D as Discovery Agent
    participant N as Negotiation Agent
    participant AWS as AWS Vendor Agent
    participant AZ as Azure Vendor Agent
    participant GCP as GCP Vendor Agent
    participant V as Verification Agent
    participant C as Compliance Agent
    participant Dec as Decision Agent

    U->>B: "8 H100s, 3-month contract, $115k budget"
    B->>D: structured requirement
    D->>AWS: A2A Agent Card request
    D->>AZ: A2A Agent Card request
    D->>GCP: A2A Agent Card request
    D-->>N: candidate vendor list

    par Simultaneous negotiation over A2A
        N->>AWS: opening offer
        AWS-->>N: counter-offer
    and
        N->>AZ: opening offer
        AZ-->>N: counter-offer
    and
        N->>GCP: opening offer
        GCP-->>N: counter-offer
    end

    N->>V: verify AWS's claimed 3-month committed-use discount rate
    V-->>N: no such tier exists -- AWS's real terms are 1yr/3yr only
    N->>AWS: challenge, renegotiate
    AWS-->>N: revised, verified offer

    N->>C: proposed deal (current best offer)
    C-->>N: rejected — exceeds budget policy
    N->>AZ: renegotiate under budget constraint
    AZ-->>N: revised offer, compliant

    N->>Dec: final compliant, verified offer + evidence
    Dec-->>U: Decision + Evidence + Reasoning
```

**Why this matters for the demo**: the two `-->>` moments where a vendor
gets challenged and a deal gets rejected are the literal, provable
difference between Pact and a static comparison tool — they only happen
because verification and compliance are real, running checks, not
decorative agent names.

---

## 4. Data & Infrastructure Layer

Where the real data comes from, how the two models divide labor, and what
runs where.

```mermaid
flowchart TB
    subgraph MCP["MCP Tool Layer"]
        PRICINGTOOL["Pricing API Tool<br/>real AWS/Azure/GCP/RunPod<br/>public pricing APIs"]
        VERIFYTOOL["Verification Tool<br/>independent claim cross-check"]
    end

    subgraph MODELS["Model Serving — two distinct jobs"]
        GEMINI["Gemini (Developer API, default;<br/>Vertex AI real, tested fallback)<br/>deep reasoning:<br/>requirement parsing,<br/>negotiation narration,<br/>ambiguous edge cases"]
        GEMMA["Gemma (self-hosted, Cloud Run)<br/>fast, cheap, high-frequency:<br/>verification pre-screening<br/>during live negotiation ticks"]
    end

    GEMMA -.->|escalate uncertain case| GEMINI

    subgraph INFRA["Infrastructure"]
        CLOUDRUN["Cloud Run<br/>app + Gemma inference service"]
        BIGQUERY["BigQuery<br/>every negotiation logged;<br/>backs the evaluation harness"]
        VERTEXAI["Vertex AI<br/>real, tested fallback only —<br/>not the default serving path"]
    end

    OTEL["OpenTelemetry tracing<br/>real spans: token usage · latency ·<br/>prompt hashes · negotiation_id — PRD §23b"]

    GEMINI -.->|fallback only, on Developer API failure| VERTEXAI
    MCP -.->|used by Discovery,<br/>Negotiation, Verification agents| MODELS
    MODELS --> CLOUDRUN
    BIGQUERY --> CLOUDRUN
    MODELS --> OTEL
    OTEL --> BIGQUERY
```

**Why Gemini and Gemma are both here, doing different jobs**: Gemma runs
locally/self-hosted for the high-frequency micro-decisions verification
needs during a live back-and-forth (many quick checks per negotiation
round) — using a large hosted model for every one of those would be slow
and unnecessary. Gemini is reserved for the actual deep reasoning: parsing
an ambiguous requirement, or narrating *why* a negotiation move was made in
plain language. This is a real model-selection decision, not two models
doing the same thing for stack-padding.

---

## 5. Evaluation Harness Pipeline

The path from "Pact saves money" as a claim to "Pact saves money" as a
provable, re-runnable result — the piece that turns the evaluation
harness (PRD §29) into something with real architectural weight, not just
a paragraph of intent.

```mermaid
flowchart LR
    CATALOGUE["Scenario Catalogue<br/>(PRD §18)<br/>fixed set of representative<br/>negotiation scenarios"] --> RUN["Full agent pipeline<br/>run once per scenario,<br/>end to end"]
    RUN --> LOG["Negotiation log<br/>offers, verification results,<br/>compliance results, outcome"]
    LOG --> BQ["BigQuery<br/>every run's full log,<br/>demo and background runs alike"]
    BQ --> AGG["Aggregate query<br/>agreement rate, avg rounds,<br/>avg savings %, compliance<br/>catches — computed via SQL"]
    AGG --> REPORT["Evaluation report<br/>real numbers from real runs,<br/>included in the submission"]
```

**Why this matters**: every number in the evaluation report traces back
through this exact pipeline to a real, individually-logged negotiation run
— there is no manual computation, no hand-picked scenario, and no step
where a plausible-looking number could be substituted for a real one. The
same BigQuery table backs both a single demo run's replay (§3, FR-10) and
the full aggregate statistics — one real record, queried two different
ways, not two separately maintained sources of truth.

---

## Glossary

- **A2A (Agent2Agent protocol)** — the real transport Pact uses for
  negotiation between the Buyer/Negotiation Agent and independent Vendor
  Agents. Not internal plumbing — this is the actual negotiation channel.
- **Agent Card** — an A2A-native way for an agent to declare its identity
  and capabilities before interaction; used here so the Discovery Agent can
  verify a Vendor Agent is who it claims to be before negotiating with it.
- **MCP (Model Context Protocol)** — wraps external tools (the real pricing
  APIs, the verification data source) so agents can call them consistently.
- **BATNA** — Best Alternative To a Negotiated Agreement; the walk-away
  point the Negotiation Agent's concession-curve logic is built around.
- **Concession curve** — the deterministic function governing how much the
  Negotiation Agent is willing to move off its opening offer over
  successive rounds, based on time/urgency and the vendor's own behavior.
  This is what keeps negotiation *real* math, not an LLM inventing numbers.
- **API Gateway** — real JWT authentication and rate limiting for
  external-facing traffic, implemented directly as `pact-core`
  middleware/dependencies rather than a separate physical gateway
  process — a disclosed choice at this single-operator scale, not a gap.
  Auth is real but off by default (no end-user accounts exist yet to
  protect); rate limiting is real and always on. TLS termination is real
  via the deployment layer (ngrok) (PRD §23a).
- **Guardrails** — the real, self-hosted prompt-injection classifier and
  Microsoft Presidio PII detector protecting FR-1's intake, the one place
  raw user input reaches a model before validation — covering both
  modalities (text/voice directly; photo via a real transcription call
  feeding the same screen). A hosted alternative (Enkrypt AI) was
  evaluated and rejected after real side-by-side testing showed this
  combination catching more real attacks with no external dependency
  (PRD §23a).
- **CRISPE** — the prompt-structuring framework (Capacity/Role, Insight,
  Statement, Personality, Experiment) both of Pact's real Gemini prompts
  are documented against (PRD §16a).
- **model_traces** — the real BigQuery table (`infra/bigquery/schema.sql`)
  every OpenTelemetry span exports to: one row per real Gemini/Gemma/Vertex
  call, with token usage, latency, a prompt hash, and (where available) a
  correlating `negotiation_id` (PRD §23b).
