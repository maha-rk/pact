# Engineering Log — Real Bugs Found and Fixed During This Build

This is not a curated highlight reel. It's every genuine defect caught
during Pact's development that was significant enough to be worth
recording — how it was found, what was actually wrong, and how it was
fixed. If a claim elsewhere in this repo's docs looks too clean, this is
where the mess that produced it is shown instead of hidden.

Every item below is real: caught via an actual test failure, an actual
live CI run, or actual production data — never invented for this log.

---

## Data integrity

**Aggregate statistics could exceed 100%.** The evaluation harness's
claim-mismatch and compliance-rejection catch-rate subqueries counted
`negotiation_events` rows without constraining them to negotiation IDs
that actually had a corresponding `negotiations` row. Since
`negotiation_events` accumulates across every test and dev run over the
project's lifetime while `negotiations` only reflects real completed
runs, the ratio could exceed the population it was supposed to be a
fraction of — caught for real when it printed a **1966%** compliance
rejection rate (116 distinct event IDs against 5 real negotiation rows).
Fixed in both `infra/bigquery/queries_aggregate.sql` and the
observability dashboard's embedded copy of the same query.

**The observability dashboard's headline number was measuring the wrong
thing.** "Agreement rate" pooled every logged negotiation — ad-hoc demo
runs and the designed evaluation catalogue together. Ad-hoc runs are
overwhelmingly the flagship happy path, so the number drifted upward
with every demo click (86.7% → 87.9% → 89.2% over three separate demo
sessions), meaning it measured how often the "Start negotiation" button
had been pressed, not how the system actually behaves. Fixed by tagging
catalogue runs with a `scenario_id` column and scoping the aggregate SQL
to catalogue-only runs — the number is now **63.6%**, computed from 11
designed scenarios (4 of which are supposed to end in no deal), and
verified to stay frozen at that value after running an ad-hoc
negotiation immediately afterward.

**Gemma's token count silently went missing.** The BigQuery exporter
reads a `tokens.total` span attribute, but Ollama's API only reports
`prompt_eval_count` and `eval_count` separately — unlike Gemini, which
provides a ready-made total via `usage_metadata`. Every real,
successful Gemma call was landing in BigQuery with `tokens_total: NULL`
despite both halves being logged correctly. Fixed by summing the two
fields at the point of capture; historical rows were backfilled from
their own already-logged `tokens_prompt`/`tokens_completion` columns
(2,804 + 1,201 = 4,005 tokens recovered, not invented).

**A test sentinel leaked into the production table.**
`tests/integration/test_tracing.py` uses a fake model name
(`"fake-model"`) to exercise span mechanics without a live model call,
normally captured by the test's own in-memory exporter. But OpenTelemetry's
`trace.set_tracer_provider()` only succeeds once per process — if
anything imports the real app before that test module runs, the real
BigQuery-backed provider wins the race, and the test's spans went to
production instead. Two `fake-model` rows reached the live
`model_traces` table and surfaced on the dashboard. Fixed at the write
layer (the exporter now filters the sentinel before it's ever loaded),
not just the read layer (the dashboard's query already excluded it, but
that alone left the table itself contaminated).

---

## Test correctness and CI

**A test that could pass without proving anything.** The distributed
Pub/Sub decoupling test used a fixed `negotiation_id` string. The
Firestore emulator persists documents for its whole process lifetime,
so a second run of the test could read a stale, already-terminal
document left over from an earlier run — passing in 2.8 seconds without
the worker actually reprocessing anything that time. Caught because
2.8 seconds was suspiciously fast for a test that spins up two real
subprocess services and waits on real Pub/Sub delivery; the genuine
run takes about 27 seconds. Fixed by minting a fresh UUID-based
negotiation ID per test invocation.

**A CI failure that wasn't a regression.** The guardrail injection test
failed in CI with a bare `assert False` after passing three consecutive
runs, with no guardrail code touched in between. Root cause: the
production guardrail deliberately swallows every failure so a screening
problem never blocks a negotiation — which also means a failed model
download and a genuinely missed attack are indistinguishable from
outside. GitHub's shared runner IPs get rate-limited by the Hugging Face
Hub harder than a developer machine, so the model occasionally fails to
download there. Fixed by adding `injection_classifier_load_error()`, so
the test can skip on a genuine infrastructure failure while still
failing loudly if the model loads and actually misses the attack —
verified both paths independently (skips with a real `OSError` when
pointed at a nonexistent model; detects the real attack at 99.9%
confidence when the model loads normally).

**Fixed sleeps instead of readiness checks caused two separate CI
failures.** The new `backend-distributed` CI job first failed because
`apt-get install` ran before the Google Cloud SDK's apt repository was
actually registered on the runner image. Fixed, then failed again
because the Pub/Sub and Firestore emulators — Java processes cold-starting
right after a ~2-minute apt install — didn't reliably finish
starting within a fixed 8-second sleep. Fixed by polling both ports for
up to 60 seconds instead of guessing a duration. A third failure after
that: the Firestore emulator specifically requires a Java 21+ JRE, but
the emulator's own apt dependencies pulled in `openjdk-8` as a
side-effect, which could shadow the Java 21 the workflow had explicitly
set up — fixed by forcing `PATH` back to the correct JDK immediately
before starting the emulator.

---

## Security and guardrails

**A hosted guardrail API missed a real attack and most of the PII in a
real test.** Enkrypt AI's hosted prompt-injection/PII detection service
was tested live against a crafted injection attempt and a realistic
quote containing a name, email, and phone number — it scored the
injection 100% safe and caught only the email, missing the name and
phone number entirely. The same two cases against a self-hosted
alternative (a fine-tuned DeBERTa injection classifier plus Microsoft
Presidio) scored the injection 99.9% INJECTION and caught all three PII
entities. Replaced rather than supplemented, based on that real,
side-by-side result — not a vendor preference.

**A CI-vs-local dependency-size mismatch.** `en_core_web_lg` (400MB) was
the original PII-detection model choice; switched to `en_core_web_sm`
(12.8MB) after confirming identical detection quality on the same real
test case, specifically to keep CI and container build times sane.

---

## Infrastructure and timing

**A vendor client timeout that was too short for reality.** `HttpVendorClient`'s
original 10-second timeout caused real, intermittent CI failures — Azure's
own internal pricing-API client uses a 30-second timeout, so the outer
client could time out while the (still legitimately running) inner call
would otherwise have succeeded. Caught via an actual GitHub Actions run
under real network latency, not assumed from reading the code. Fixed by
raising the outer timeout to 35 seconds.

**A billing assumption that turned out to be wrong, caught before
spending money.** Diagnosed that Gemini's Developer API was capped at
20 requests/day despite `pact-hackathon` having real, active GCP
billing. The apparent fix — minting a new Gemini API key scoped to the
billed project — was tested for real: the API was enabled, a properly
restricted key was created, and a live call against it returned
`429: "Your prepayment credits are depleted."` The $300 trial credit
that funds the Vertex AI fallback does not apply to the Gemini Developer
API, which requires separately prepaid credits. Rather than spend real
money to chase a marginal reliability gain the existing Vertex AI
fallback already covers, the unused key was deleted and the finding
documented instead.

---

## Documentation drift

**Docs said things that stopped being true.** An end-to-end audit (not
triggered by a bug report — a deliberate check of every claim against
actual current state) found four real mismatches in one pass: a
dashboard read-filter that existed in the deployed container but had
never been committed to git; a Dockerfile comment stating "Deliberately
NOT included: GCP credentials" that became false the moment a
scoped, read-only BigQuery key started being mounted for the live demo;
README deployment instructions that, followed exactly, produced a
container whose Observability tab couldn't reach BigQuery (the
credential-mount step was missing from the documented command); and a
PRD with no explicit non-claim about ERP/SAP/Coupa integration despite
positioning Pact directly against those incumbents elsewhere in the same
document. All four fixed in the same pass they were found.

---

The pattern across all of the above: every one of these was caught by
actually running something real — a live test, a live API call, a live
CI job, a live deployed container — not by code review alone. That's
also why this list exists: a system that never reports finding anything
wrong during its own construction is less credible than one that shows
its work.
