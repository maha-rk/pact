"""Real observability dashboard endpoint test
(`pact/api/routes_observability.py`) -- against the real, live BigQuery
data when credentials are available (local dev, this build's own
project). The endpoint's own graceful degradation (never a 500) is what
lets the first test run unconditionally, including in CI, where no
BigQuery credentials are configured.

`pact.main` is imported inside the test function, not at module level --
importing it at collection time would trigger the real
`configure_tracing()` and install the real Console+BigQuery
TracerProvider as the process-wide OTel singleton before
`test_tracing.py`'s own module-level test provider gets a chance to
(OTel's `set_tracer_provider` only succeeds once per process; a second
call is silently ignored). `tests/integration/test_api.py` uses the same
deferred-import pattern for exactly this reason."""

from __future__ import annotations

import pytest

from pact.api.routes_observability import get_observability_summary


def test_observability_summary_never_errors_and_has_a_well_formed_shape():
    from fastapi.testclient import TestClient

    from pact.main import app

    with TestClient(app) as client:
        resp = client.get("/observability/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "available" in body
    if body["available"]:
        assert isinstance(body["model_traces"], list)
        assert body["negotiations"] is None or "total_runs" in body["negotiations"]
    else:
        assert body["error"]


def test_when_real_bigquery_data_is_reachable_the_aggregate_rates_are_valid_percentages():
    """A real bug caught during this build: negotiation_events
    accumulates across every historical run, so an aggregate query not
    constrained to negotiation_ids present in `negotiations` can report a
    >100% catch rate (116 distinct event negotiation_ids vs. 5 real
    `negotiations` rows produced an impossible 1966% figure before the
    fix in routes_observability.py / queries_aggregate.sql). Assert the
    fix holds against live data when it's actually reachable."""
    result = get_observability_summary()
    if not result.available or result.negotiations is None:
        pytest.skip("BigQuery not reachable in this environment")
    assert 0.0 <= result.negotiations.claim_mismatch_catch_rate <= 1.0
    assert 0.0 <= result.negotiations.compliance_rejection_rate <= 1.0
    assert 0.0 <= result.negotiations.agreement_rate <= 1.0
