# Pact — Product Requirements Document

**The decision infrastructure for autonomous B2B commerce.**

| | |
|---|---|
| Track | B2B Services — Problem Statement #7, *Vendor Evaluation* |
| Official problem text | "Vendor evaluation remains time-consuming and highly manual." |
| Event | AI Agent Builder Series 2026 — National Finale (HiDevs × AI House) |
| Date / Venue | 8 Aug 2026, Google Kyoto West Block, Bengaluru |
| Author | Mahashri RK (solo) |
| Status | Pre-build — architecture and scope locked |

---

## 1. Executive Summary

Pact is a six-agent system that autonomously negotiates B2B procurement
deals in real time. A Buyer Agent, representing the user's organization,
negotiates directly against independent Vendor Agents using the Agent2Agent
(A2A) protocol as the literal transport — not internal plumbing, the actual
product mechanic. Every number the system relies on is grounded in live,
public, independently verifiable data; nothing is fabricated, mocked, or
presented as real when it isn't.

The launch showcase is cloud infrastructure procurement — a buyer needs
GPU/compute capacity, and Pact's agents discover, negotiate with, verify,
and select between AWS, Azure, GCP, and RunPod in real time, live, in front
of an audience. This category was chosen deliberately: it's the one B2B
procurement domain with clean, free, real-time public pricing APIs, which
means every number in the demo is checkable by a skeptical judge on the
spot. The system is architected to generalize to other procurement
categories over time (§9), but nothing outside cloud compute is faked to
make the demo look broader today.

The thesis is a category shift, not a feature: existing procurement
software (SAP Ariba, Coupa) digitizes the *paperwork* of procurement — a
human still reads every quote and makes every decision. Pact removes the
human from the negotiation loop, surfacing only the final, evidence-backed
decision for approval.

---

## 2. Problem

Procurement negotiation today is slow and manual by construction, not by
accident:

- A human has to read every vendor's quote, understand it, and compare it
  against every other vendor's quote, often in incompatible formats.
- Negotiation happens sequentially over email or calls, typically across
  days or weeks, because a human can only hold one conversation at a time.
- There is no systematic way to verify a vendor's claim (a quoted discount,
  a stated capability) against independent ground truth — the buyer either
  trusts the vendor's word or spends more time manually checking.
- Existing procurement platforms (SAP Ariba, Coupa) automate the
  *workflow* around this — requisitions, approvals, supplier catalogs,
  invoice matching — but not the negotiation itself. The decision-maker is
  still a human, reading, at human speed.

This is a real, acknowledged cost center for any organization with
recurring vendor spend, and it scales badly: the more vendors and the more
frequently pricing changes (as with cloud compute, where prices and
discount tiers shift often), the more manual effort procurement demands.

## 3. Insight

The relevant shift isn't "make the existing procurement software smarter
with an AI feature." It's that as AI agents become standard infrastructure
for every organization, procurement stops being "a person compares
vendors" and becomes "a Buyer Agent transacts directly with Vendor Agents."
That needs a **decision engine**, not an assistant that reads documents
faster than a human. A decision engine autonomously discovers vendors,
negotiates under real constraints, verifies every claim against
independent evidence, and hands back a final, explainable decision — not a
summary the human still has to act on.

---

## 4. Users & Personas

**Primary persona — Procurement/Finance lead at an infrastructure-heavy
company.** An AI startup or SaaS company with recurring, meaningful cloud
spend. Today they (or an engineer without procurement training) manually
compares AWS/Azure/GCP pricing pages, negotiates enterprise discounts by
email over days, and has no systematic way to verify a sales rep's claimed
discount against what's actually published. Wants: lower spend, less time
spent on this, confidence the decision was actually the best available
option, not just the first acceptable one.

**Secondary persona — a technical founder wearing every hat.** Doesn't have
a dedicated procurement function at all; currently either overpays by
accepting the first quote or under-invests the time to negotiate properly
because it competes with building the actual product. Wants procurement to
be something that happens automatically in the background, at the quality
level of a specialist, without hiring one.

**Judge/evaluator persona (for the finale specifically)** — a technical or
business mentor evaluating ~10 finalist teams in a 6-minute slot each.
Needs to understand the value proposition in the first 30 seconds, see
genuine autonomous multi-agent behavior (not a scripted chat), and be able
to challenge a claim on stage and have it hold up — this shapes the demo
design as much as the "real" end users do.

---

## 5. Competitive Analysis

### 5.1 Incumbent enterprise software — SAP Ariba, Coupa

These platforms digitize procurement *paperwork*: requisitions, approval
chains, supplier catalogs, spend analytics, invoice matching. A human still
reads every quote and makes every real decision — the software moves forms
faster, it doesn't decide. They are also closed platforms: a supplier has
to onboard onto Ariba Network specifically to participate, which is a real
adoption barrier. Pact's differentiation is structural, not cosmetic: it
removes the human from the negotiation loop entirely (surfacing only the
final decision for approval), and is built on an open protocol (A2A) —
any vendor with an A2A-compliant agent can participate without
platform-specific onboarding.

### 5.2 Direct competitors at this event

Six real competitor repos from this same hackathon series were reviewed
directly (not assumed) as of 2026-08-04:

| Project | Track | What it does | Relevance |
|---|---|---|---|
| SentinelOps-X | Operational Bottleneck Detection | Predictive ops monitoring, deterministic simulation | Different problem; validates that track is crowded |
| FlowLens AI | Operational Bottleneck Detection | 5-layer bottleneck analysis pipeline | Same track as above; also crowded |
| IntelliAsha | HealthTech | Voice-first rural health surveillance, real multi-agent swarm | Different problem; strong build, not a competitor to this idea |
| KYRO | HealthTech | Ambient elderly health monitoring | Early-stage, different problem |
| **FabricMart (B2B Textile Marketplace)** | B2B, adjacent | AI shopping assistant for fabric buyers/suppliers | **Closest adjacent entry — explicitly confirmed no agent-to-agent negotiation or automated vendor evaluation.** Search/recommendation only. |
| PulseOps-AI | Healthcare ops | Multi-agent hospital triage/resource coordination | Different problem; internal-to-one-org coordination, not cross-org negotiation |

**Conclusion**: none of the six do agent-to-agent negotiation. The closest
adjacent entry (FabricMart) explicitly does not.

### 5.3 Closest real precedent — VeganFlow

The most important comparison isn't at this event at all: **VeganFlow**
(3rd place, Kaggle "Agents Intensive Capstone," Enterprise Agents track)
already built agent-to-agent procurement negotiation via A2A and Google
ADK — a Procurement Agent negotiating with vendor agents. The core
mechanic is not literally unprecedented, and Pact is deliberately scoped
to clear this specific, real bar rather than pretend it doesn't exist:

| | VeganFlow (3rd place) | Pact |
|---|---|---|
| Vendor data | 11 simulated agents, built by the same team, fixed internal price target pulled from memory | Real, live, external public pricing APIs (AWS/Azure/GCP/RunPod) |
| Negotiation | Single vendor identified, sequential, one counter-offer | Multiple vendors negotiated with **simultaneously**, live competitive pressure |
| Verification | None — the counter-offer is accepted at face value | Verification Agent cross-checks every vendor claim against real external data, live |
| Agent identity | Not addressed | A2A Agent Cards checked by the Discovery Agent before negotiation begins |
| Evidence in output | Not surfaced | Every decision ships as Decision / Evidence / Reasoning — no fabricated composite score |

The same competition's **1st place**, Chaos Playbook Engine, beat VeganFlow
specifically through empirical rigor (14,000 parametric experiments, real
statistics) rather than narrative or a single demo — this directly informs
Pact's evaluation harness requirement (§8): don't just run one live demo,
produce real aggregate evidence across many runs.

### 5.4 Cross-hackathon pattern (NVIDIA, Microsoft, additional Kaggle entries)

Reviewing winners across several other agentic-AI hackathons (NVIDIA NeMo
Toolkit hackathon, Microsoft AI Agents Hackathon's RiskWise, Devpost's
SalesShortcut, Kaggle's Coderama) surfaces a consistent pattern, not a
coincidence:

1. **Winners automate decisions, not tasks** — the value is "helps decide,"
   not "summarizes faster." RiskWise doesn't summarize supply-chain data,
   it helps decide risk response; SalesShortcut doesn't write emails, it
   generates revenue.
2. **Winners sit close to money** — procurement, sales, logistics, supply
   chain, all have an obvious, quantifiable business impact a judge grasps
   instantly, unlike more diffuse categories.
3. **Winners have a "future of work" framing** — an autonomous agent
   *organization* replacing a human team's function, not a copilot bolted
   onto an existing human workflow.
4. **Winners are complete, working pipelines**, not the cleverest fragment —
   NVIDIA's 1st place won for a full simulation-to-real-deployment
   pipeline specifically.
5. **Winners show transparent, auditable reasoning** — RiskWise won partly
   for timestamped decision logs and interactive, verifiable
   explainability, not just a correct-looking output.
6. **Trust/verification of the agent itself is a recurring theme** across
   the wider agentic-AI hackathon space (a separate Cheqd-ecosystem
   hackathon's projects — Identone, Kith, Dail Bot, Trusty Bytes, crdbl —
   were built almost entirely around this question, in a different
   ecosystem but the same underlying concern).

Pact is deliberately designed to hit all six patterns: a decision engine
(§3), directly tied to real procurement spend (§2), framed as "Buyer Agents
transact with Vendor Agents" rather than "an assistant helps you compare
vendors," built end-to-end rather than partially, with a visible audit
trail (Decision/Evidence/Reasoning, §7), and A2A Agent Card verification
addressing agent-identity trust (§7).

---

## 6. Solution — What Pact Actually Does

A user states a real requirement once (voice, or a photographed invoice/
pricing screenshot read by Gemini vision — see §7.3). From there, entirely
autonomously:

1. The requirement is parsed into structured constraints (budget, specs,
   contract terms).
2. Candidate vendors are discovered and their identities verified via A2A
   Agent Cards.
3. Real-time, **simultaneous** negotiation runs against every discovered
   vendor over A2A — not one conversation at a time.
4. Every vendor claim made during negotiation is checked against
   independent, real external data live; a mismatch triggers a challenge
   and renegotiation, not silent acceptance.
5. Policy constraints (budget ceiling, blocked vendors, required
   certifications) are enforced before any deal is finalized; a violation
   forces renegotiation.
6. A final decision is produced in a fixed, evidence-first format and
   rendered as a real downloadable agreement.

See `ARCHITECTURE.md` §3 for the full step-by-step sequence of a real run,
including the two moments (a caught lie, a rejected deal) that make this
demonstrably more than a chat between two LLMs.

---

## 7. Detailed Requirements

### 7.1 The six agents

**Buyer Agent** — Inputs: a natural-language requirement (voice-transcribed
or typed) or a vision-extracted set of numbers from a photographed
document. Output: a structured requirement object (budget ceiling,
specification, contract length, any hard constraints) plus the negotiation
strategy parameters (reservation price, BATNA) derived from it. Uses
Gemini for the parsing step, since real user input is often ambiguous
("a few thousand a month" needs interpretation, not just extraction).

**Discovery Agent** — Input: the structured requirement. Output: a list of
candidate Vendor Agents, each verified via its A2A Agent Card (declared
identity + capabilities) before being handed to the Negotiation Agent. For
the launch showcase, this resolves to AWS, Azure, GCP, and RunPod vendor
agents. Uses MCP to query the discovery/pricing-tool layer.

**Negotiation Agent** — The core mechanic. Runs real, deterministic
concession-curve negotiation (not LLM improvisation) against every
discovered vendor **simultaneously**: an opening offer, evaluation of each
vendor's counter-offer against the reservation price and BATNA, and
successive concessions governed by a time-decay function, not an LLM
free-styling a number. Gemini is used only to *narrate* why a given move
was made in plain language for the live dashboard and the final reasoning
output — it does not decide the number. Communicates with Vendor Agents
exclusively over A2A.

**Compliance Agent** — Input: the current best offer from negotiation.
Checks it against real, explicit policy rules (budget ceiling, any blocked
vendor list, required certifications/compliance attributes). If a rule is
violated, it rejects the deal and sends it back to the Negotiation Agent
with the specific violated constraint — a real gate, not a cosmetic check
that always passes.

**Verification Agent** — Input: any factual claim a vendor makes during
negotiation (a quoted price, a stated discount, a capacity claim). Checks
it against the real, independent external pricing API via MCP. Uses Gemma
(self-hosted, low-latency) for the high-frequency plausibility pre-screen
during rapid negotiation ticks, escalating to Gemini only for genuinely
ambiguous cases — a deliberate two-tier model-selection decision, not
duplicate model usage. On a mismatch, flags it visibly and sends the
negotiation back for a challenge/renegotiation round.

**Decision Agent** — Input: the final compliant, verified offer. Output: a
fixed structure —
```
Decision: <vendor selected>
Evidence: [pricing source URL, compliance check result, capacity/region constraints]
Reasoning: <plain-language justification tied directly to the evidence>
```
Deliberately never a fabricated composite score (no "confidence: 87%" with
no ground truth) — every field traces to something real and checkable.
Rendered as a real downloadable agreement document.

### 7.2 Protocols

- **A2A** is the literal transport for negotiation between the Negotiation
  Agent and each independent Vendor Agent, and carries the Agent Cards used
  for identity verification. This is the actual product mechanic, not
  internal plumbing — most competing systems (per §5) use "multi-agent" to
  mean agents coordinating *within* one organization; Pact's agents
  negotiate *across* organizational boundaries.
- **MCP** wraps every external tool call: the real pricing APIs (AWS EC2
  Pricing API, Azure Retail Prices API, GCP Cloud Billing Catalog API,
  RunPod's public pricing), the independent verification data source, and
  the voice/vision input tools.
- **ADK** orchestrates the six-agent graph, including the two feedback
  loops described in `ARCHITECTURE.md` §2.

### 7.3 Input modalities

- **Voice** — Web Speech API captures a spoken requirement; Gemini parses
  it into the structured requirement object.
- **Vision** — a photographed real invoice or pricing screenshot is read by
  Gemini's native vision capability, extracting the actual numbers
  present in the image. This has zero fabrication risk by construction:
  every number it produces is literally visible in the photo, not
  inferred or assumed.

### 7.4 Non-functional requirements

- **No fabricated numbers, anywhere** — the hardest constraint on this
  project, applied to every UI element, log entry, and README claim, not
  just the negotiation logic. A number is either real (traced to a live
  API call, a real computation, or something literally read from an
  uploaded image) or explicitly and visibly disclosed as an estimate/mock.
- **Live negotiation must complete within a demo-appropriate window**
  (target: full negotiation-to-decision cycle under ~60 seconds) so it
  works inside a 6-minute judge slot without dead air.
- **Every negotiation is logged** (BigQuery) regardless of whether it's a
  "real" demo run or a background evaluation-harness run, so the aggregate
  statistics in §8 are drawn from genuine system behavior, not a curated
  subset.
- **Graceful, visible degradation** — if a live external pricing API is
  unreachable during the actual demo, the system must disclose that
  plainly (matching the honesty precedent set on the Prism project's
  provider-cascade work), never silently substitute a plausible-looking
  fake number.

---

## 8. Evidence, Not Narrative — the Evaluation Harness

The closest real reference class (§5.3) was won specifically by proving
claims empirically rather than through a single polished demo. Pact adopts
the same strategy directly: since every negotiation is already logged to
BigQuery, the negotiation engine is run across many scenarios ahead of the
finale (varying budget, requirement specifics, and vendor pricing
conditions), and the results are reported as real aggregate statistics —
average savings percentage achieved, negotiation success rate, and average
rounds-to-agreement — included in the submission alongside the one live
demo run, not instead of it.

---

## 9. Roadmap (stated as vision, not simulated live)

- **Today (finale build)**: cloud infrastructure procurement only — the one
  category with clean, free, live public pricing data, so every number in
  the demo is independently checkable by a skeptical judge.
- **Near-term**: additional procurement categories, added only as real
  public pricing data sources are identified for them — explicitly not
  simulated ahead of having a real data source, per §7.4's non-fabrication
  requirement.
- **Long-term**: Pact as an open, A2A-native commerce layer where any
  organization's own vendor agent can plug in directly, without the
  proprietary platform onboarding that closed systems like Ariba Network
  currently require.

---

## 10. Explicit Non-Goals for This Build

Scoped out deliberately, with reasoning, to protect the ~4-day build
window and the no-fabrication principle — not omitted by oversight:

- **No live multi-category negotiation** (CRM, marketing, legal services in
  the same demo run) — no clean, real, live public pricing data exists for
  these categories on this timeline; simulating it would mean fabricating
  numbers, which is the one thing this project is built not to do.
- **No "Contract War Room" legal-risk scoring** — a Legal Agent producing a
  risk score without a real, grounded legal database is exactly the
  fabricated-confidence pattern (a plausible-looking "Risk: Medium" label
  with no real basis) this project exists to avoid. Mentioned only as
  possible future scope, never built or claimed as working.
- **No full blockchain/DID-based agent-identity system** — A2A Agent Cards
  are the correctly-scoped version of the same "verify the agent you're
  dealing with" concern (§5.4), achievable in the available time; a
  from-scratch decentralized-identity system is not.

---

## 11. Risks & Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Negotiation logic looks scripted/gimmicky ("LLM pretending to negotiate") | This is the single biggest way this idea fails, per external review during design | Deterministic concession-curve/BATNA logic drives every number; Gemini only narrates, never decides |
| Live external API failure during the actual demo | Would break the "everything is real and live" premise | Visible, honest degradation disclosure (§7.4) rather than a silent fake fallback |
| Judges don't immediately grasp why cross-org agent negotiation is hard/novel | The idea is more abstract than a visceral human-facing problem | Demo opens with the business framing and closes with the evaluation-harness numbers, not just the mechanic |
| Skeptical judge says "this is just Ariba with AI" | Real incumbent competitors exist and are well-funded | The Coupa/Ariba differentiation (§5.1) is structural (removes the human from the loop, open protocol vs. closed platform), not cosmetic — survives direct questioning |
| Scope creep re-introduces fabrication risk (multi-category, legal scoring) | Discussed and explicitly rejected during design (§10) | Non-goals section exists specifically to hold this line under time pressure |

---

## 12. Success Criteria for the Finale Submission

- Negotiation runs live, end-to-end, against real external pricing data
  with zero fabricated numbers anywhere in the demo, UI, or README.
- The Verification Agent demonstrably catches at least one real claim/data
  mismatch live.
- The Compliance Agent demonstrably rejects at least one deal live, forcing
  a visible renegotiation.
- The evaluation harness produces real aggregate statistics from multiple
  runs, not a single cherry-picked scenario.
- The GitHub repo contains this PRD, the architecture diagram, full working
  source code, an honest README, and setup instructions — per the official
  submission requirements.

---

## 13. Glossary

See `ARCHITECTURE.md` for the full glossary (A2A, Agent Card, MCP, BATNA,
concession curve) shared between both documents.
