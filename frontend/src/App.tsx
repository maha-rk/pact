import { useEffect, useRef, useState } from "react";
import "./App.css";
import { createNegotiation, parseRequirementFromImage, parseRequirementFromText } from "./api";
import type { NegotiationState } from "./types";
import type { ParsedRequirement } from "./api";
import { DecisionView } from "./components/DecisionView";
import { ReplayTimeline } from "./components/ReplayTimeline";
import { ObservabilityDashboard } from "./components/ObservabilityDashboard";
import { LandingPage } from "./components/LandingPage";
import { PactMark } from "./components/PactMark";

// Non-standard browser API (Chrome/Edge/Safari); no official TS lib types.
type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  start: () => void;
  onresult: ((event: { results: { [index: number]: { [index: number]: { transcript: string } } } }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as (new () => SpeechRecognitionLike) | null;
}

const FLAGSHIP_DEFAULTS = {
  gpu_count: 8,
  contract_months: 3,
  budget_ceiling_usd: 115000,
  raw_input: "Need 8 H100 GPUs, 3-month contract, $115,000 budget",
  initial_claimed_discounts: { aws: 0.25, azure: 0.8152 },
};

type Tab = "decision" | "replay";
type View = "landing" | "negotiate" | "observability";

function IconNegotiate() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 12h8" />
      <path d="M8 12l3-3M8 12l3 3" />
      <path d="M16 12l-3-3M16 12l-3 3" />
      <rect x="2" y="6" width="6" height="12" rx="1.5" />
      <rect x="16" y="6" width="6" height="12" rx="1.5" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19V10" />
      <path d="M11 19V5" />
      <path d="M18 19v-7" />
      <path d="M3 21h18" />
    </svg>
  );
}

function App() {
  const [view, setView] = useState<View>("landing");
  // The landing page's "How it works" / "Evidence" nav links are
  // anchors into content that only exists when the landing page is
  // mounted. From inside the app, clicking them needs to switch views
  // first and then scroll once that content actually renders --
  // hence the pending target instead of a plain href.
  const [pendingScrollTarget, setPendingScrollTarget] = useState<string | null>(null);
  const [form, setForm] = useState(FLAGSHIP_DEFAULTS);
  const [state, setState] = useState<NegotiationState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("decision");
  const [intakeStatus, setIntakeStatus] = useState<string | null>(null);
  const [guardrailWarnings, setGuardrailWarnings] = useState<string[]>([]);
  const [intakeBusy, setIntakeBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (view !== "landing" || !pendingScrollTarget) return;
    const el = document.getElementById(pendingScrollTarget);
    el?.scrollIntoView();
    setPendingScrollTarget(null);
  }, [view, pendingScrollTarget]);

  const goToLandingSection = (id: string) => {
    setPendingScrollTarget(id);
    setView("landing");
  };

  const applyParsedRequirement = (parsed: ParsedRequirement) => {
    const found: string[] = [];
    const missing: string[] = [];
    setForm((prev) => {
      const next = { ...prev, raw_input: parsed.raw_input };
      if (parsed.gpu_count != null) {
        next.gpu_count = parsed.gpu_count;
        found.push(`${parsed.gpu_count} GPUs`);
      } else {
        missing.push("GPU count");
      }
      if (parsed.contract_months != null) {
        next.contract_months = parsed.contract_months;
        found.push(`${parsed.contract_months}-month contract`);
      } else {
        missing.push("contract length");
      }
      if (parsed.budget_ceiling_usd != null) {
        next.budget_ceiling_usd = parsed.budget_ceiling_usd;
        found.push(`$${parsed.budget_ceiling_usd.toLocaleString()} budget`);
      } else {
        missing.push("budget");
      }
      return next;
    });
    const foundText = found.length ? `Extracted: ${found.join(", ")}.` : "Nothing recognizable was extracted.";
    const missingText = missing.length
      ? ` Not found in the input (left as-is, please review): ${missing.join(", ")}.`
      : "";
    setIntakeStatus(foundText + missingText);
    setGuardrailWarnings(parsed.guardrail_warnings ?? []);
  };

  const handlePhotoUpload = async (file: File) => {
    setIntakeBusy(true);
    setIntakeStatus(null);
    setGuardrailWarnings([]);
    setError(null);
    try {
      const parsed = await parseRequirementFromImage(file);
      applyParsedRequirement(parsed);
    } catch {
      setIntakeStatus("Couldn't read that photo right now — please fill in the fields below manually.");
    } finally {
      setIntakeBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleVoiceInput = () => {
    const Recognition = getSpeechRecognition();
    if (!Recognition) {
      setError("Voice input isn't supported in this browser (try Chrome or Edge).");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.onresult = async (event) => {
      const transcript = event.results[0][0].transcript;
      setListening(false);
      setIntakeBusy(true);
      setIntakeStatus(null);
      setError(null);
      try {
        const parsed = await parseRequirementFromText(transcript);
        applyParsedRequirement(parsed);
      } catch {
        setIntakeStatus(`Heard "${transcript}", but couldn't extract fields right now — please fill them in manually.`);
      } finally {
        setIntakeBusy(false);
      }
    };
    recognition.onerror = (event) => {
      setListening(false);
      setIntakeStatus(`Voice recognition error: ${event.error}`);
    };
    recognition.onend = () => setListening(false);
    setListening(true);
    recognition.start();
  };

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

  if (view === "landing") {
    return (
      <LandingPage
        onEnterNegotiate={() => setView("negotiate")}
        onEnterObservability={() => setView("observability")}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <button type="button" className="app-brand" onClick={() => setView("landing")}>
          <PactMark size={28} />
          <span className="brand-name">Pact</span>
        </button>
        <nav className="landing-nav">
          <button type="button" onClick={() => goToLandingSection("how-it-works")}>How it works</button>
          <button type="button" onClick={() => setView("negotiate")}>Live Negotiation</button>
          <button type="button" onClick={() => goToLandingSection("evidence")}>Evidence</button>
          <a href="https://github.com/maha-rk/pact/blob/main/docs/PRD.md" target="_blank" rel="noreferrer">PRD</a>
          <a href="https://github.com/maha-rk/pact/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer">Architecture</a>
        </nav>
        <a
          className="app-topbar-link"
          href="https://github.com/maha-rk/pact"
          target="_blank"
          rel="noreferrer"
        >
          View source on GitHub
        </a>
      </header>

      <div className="app-toggle-row">
        <div className="app-toggle">
          <button
            type="button"
            className={`app-toggle-item ${view === "negotiate" ? "active" : ""}`}
            onClick={() => setView("negotiate")}
          >
            <IconNegotiate />
            Negotiate
          </button>
          <button
            type="button"
            className={`app-toggle-item ${view === "observability" ? "active" : ""}`}
            onClick={() => setView("observability")}
          >
            <IconChart />
            Observability
          </button>
        </div>
      </div>

      <div className="main">
        <header className="topbar">
          <h1>{view === "negotiate" ? "Negotiate" : "Observability"}</h1>
          <p className="topbar-subtitle">
            {view === "negotiate"
              ? "Discover vendors, verify claims, and settle a compliant deal — real HTTP, real pricing, real evidence."
              : "Real OpenTelemetry spans and negotiation outcomes, queried live from BigQuery."}
          </p>
        </header>

        <div className="content">
          {view === "observability" ? (
            <section className="panel">
              <ObservabilityDashboard />
            </section>
          ) : (
            <>
              <section className="panel requirement-form">
                <h2>Requirement</h2>
                <div className="intake-row">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={intakeBusy || listening}
                  >
                    📷 Upload a photo of a quote/invoice
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/heic,image/heif"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handlePhotoUpload(file);
                    }}
                  />
                  <button type="button" className="btn-secondary" onClick={handleVoiceInput} disabled={intakeBusy || listening}>
                    {listening ? "🎙️ Listening..." : "🎙️ Speak your requirement"}
                  </button>
                  {intakeBusy && <span className="intake-status">Extracting with Gemini...</span>}
                </div>
                {intakeStatus && <p className="intake-status">{intakeStatus}</p>}
                {guardrailWarnings.length > 0 && (
                  <ul className="guardrail-warnings">
                    {guardrailWarnings.map((w, i) => (
                      <li key={i}>⚠️ {w}</li>
                    ))}
                  </ul>
                )}
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
                <button className="btn-primary" onClick={runNegotiation} disabled={loading}>
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
                <section className="panel results">
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
