import { useEffect, useState } from "react";
import { getObservabilitySummary } from "../api";
import type { ObservabilitySummary } from "../types";

const MODEL_LABELS: Record<string, string> = {
  "gemma3:4b": "Gemma (self-hosted)",
  "gemini-flash-latest": "Gemini (Developer API)",
  "gemini-2.5-flash": "Vertex AI (fallback)",
};

function pct(value: number | null): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function ms(value: number | null): string {
  if (value == null) return "—";
  return `${value.toLocaleString()} ms`;
}

export function ObservabilityDashboard() {
  const [data, setData] = useState<ObservabilitySummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getObservabilitySummary()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((e) => {
        if (!cancelled) setData({ available: false, error: e instanceof Error ? e.message : String(e), model_traces: [], negotiations: null });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p className="intake-status">Loading real statistics from BigQuery...</p>;
  }

  if (!data || !data.available) {
    return (
      <div className="observability-unavailable">
        <p>
          BigQuery isn't reachable from this environment right now, so there's nothing real to
          show — no numbers are invented here.
        </p>
        {data?.error && <p className="observability-error-detail">{data.error}</p>}
      </div>
    );
  }

  const maxCallCount = Math.max(1, ...data.model_traces.map((r) => r.call_count));

  return (
    <div className="observability-dashboard">
      <h3>Model calls (real OpenTelemetry spans, BigQuery `model_traces`)</h3>
      {data.model_traces.length === 0 ? (
        <p className="intake-status">No model calls logged yet — run a negotiation first.</p>
      ) : (
        <div className="trace-bars">
          {data.model_traces.map((row) => (
            <div className="trace-bar-row" key={row.model ?? "unknown"}>
              <div className="trace-bar-label">
                {MODEL_LABELS[row.model ?? ""] ?? row.model ?? "unknown"}
                <span className="trace-bar-count">{row.call_count} calls</span>
              </div>
              <div className="trace-bar-track">
                <div
                  className="trace-bar-fill"
                  style={{ width: `${(row.call_count / maxCallCount) * 100}%` }}
                />
              </div>
              <div className="trace-bar-stats">
                <span>avg latency: {ms(row.avg_latency_ms)}</span>
                <span>tokens: {row.total_tokens?.toLocaleString() ?? "—"}</span>
                <span className={row.error_rate && row.error_rate > 0 ? "trace-error" : ""}>
                  error rate: {pct(row.error_rate)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <h3>Negotiation outcomes (real aggregate SQL, BigQuery `negotiations` + `negotiation_events`)</h3>
      {!data.negotiations || data.negotiations.total_runs === 0 ? (
        <p className="intake-status">
          No negotiations logged yet — run one, or `python scripts/run_catalogue.py`.
        </p>
      ) : (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-value">{data.negotiations.total_runs}</div>
            <div className="stat-label">Total runs</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{pct(data.negotiations.agreement_rate)}</div>
            <div className="stat-label">Agreement rate</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{data.negotiations.avg_rounds_to_agreement ?? "—"}</div>
            <div className="stat-label">Avg rounds</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{pct(data.negotiations.avg_savings_pct)}</div>
            <div className="stat-label">Avg savings</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{pct(data.negotiations.claim_mismatch_catch_rate)}</div>
            <div className="stat-label">Claim mismatch catch rate</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{pct(data.negotiations.compliance_rejection_rate)}</div>
            <div className="stat-label">Compliance rejection rate</div>
          </div>
        </div>
      )}
    </div>
  );
}
