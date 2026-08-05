import { useState } from "react";
import "./App.css";
import { createNegotiation } from "./api";
import type { NegotiationState } from "./types";
import { DecisionView } from "./components/DecisionView";
import { ReplayTimeline } from "./components/ReplayTimeline";

const FLAGSHIP_DEFAULTS = {
  gpu_count: 8,
  contract_months: 3,
  budget_ceiling_usd: 115000,
  raw_input: "Need 8 H100 GPUs, 3-month contract, $115,000 budget",
  initial_claimed_discounts: { aws: 0.25, azure: 0.8152 },
};

type Tab = "decision" | "replay";

function App() {
  const [form, setForm] = useState(FLAGSHIP_DEFAULTS);
  const [state, setState] = useState<NegotiationState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("decision");

  const runNegotiation = async () => {
    setLoading(true);
    setError(null);
    setState(null);
    try {
      const result = await createNegotiation(form);
      setState(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header>
        <h1>Pact</h1>
        <p className="tagline">Autonomous B2B procurement negotiation</p>
      </header>

      <section className="requirement-form">
        <h2>Requirement</h2>
        <div className="form-grid">
          <label>
            GPU count
            <input
              type="number"
              value={form.gpu_count}
              onChange={(e) => setForm({ ...form, gpu_count: Number(e.target.value) })}
            />
          </label>
          <label>
            Contract months
            <input
              type="number"
              value={form.contract_months}
              onChange={(e) => setForm({ ...form, contract_months: Number(e.target.value) })}
            />
          </label>
          <label>
            Budget ceiling (USD)
            <input
              type="number"
              value={form.budget_ceiling_usd}
              onChange={(e) => setForm({ ...form, budget_ceiling_usd: Number(e.target.value) })}
            />
          </label>
        </div>
        <label className="raw-input-label">
          Requirement (as stated)
          <input
            type="text"
            value={form.raw_input}
            onChange={(e) => setForm({ ...form, raw_input: e.target.value })}
          />
        </label>
        <button onClick={runNegotiation} disabled={loading}>
          {loading ? "Negotiating..." : "Start negotiation"}
        </button>
        {error && <div className="error">Request failed: {error}</div>}
        {loading && (
          <p className="loading-note">
            Negotiating simultaneously against every discovered vendor over
            real HTTP, verifying claims against real pricing data...
          </p>
        )}
      </section>

      {state && (
        <section className="results">
          <div className="tabs">
            <button className={tab === "decision" ? "active" : ""} onClick={() => setTab("decision")}>
              Decision / Evidence / Reasoning
            </button>
            <button className={tab === "replay" ? "active" : ""} onClick={() => setTab("replay")}>
              Negotiation Replay ({state.events.length} events)
            </button>
          </div>
          {tab === "decision" ? (
            <DecisionView state={state} onUpdated={setState} />
          ) : (
            <ReplayTimeline state={state} />
          )}
        </section>
      )}
    </div>
  );
}

export default App;
