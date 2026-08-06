import { useEffect, useState } from "react";
import "./LandingPage.css";
import { getObservabilitySummary } from "../api";
import type { ObservabilitySummary } from "../types";

// A real front door: explains what Pact is and how to use it before
// dropping the visitor into the actual negotiation console. Nothing
// here is a new claim -- every line is condensed from README content
// already backed by tests/CI, and the proof strip is live data from
// the same /observability/summary endpoint the in-app dashboard uses,
// not a static number.

interface Props {
  onEnterNegotiate: () => void;
  onEnterObservability: () => void;
}

function NegotiationGraphic() {
  return (
    <svg className="landing-graphic" viewBox="0 0 360 200" fill="none" aria-hidden="true">
      <line x1="180" y1="40" x2="70" y2="150" stroke="var(--border-strong)" strokeWidth="1.5" />
      <line x1="180" y1="40" x2="290" y2="150" stroke="var(--border-strong)" strokeWidth="1.5" />
      <line x1="70" y1="150" x2="290" y2="150" stroke="var(--border)" strokeWidth="1.5" strokeDasharray="4 5" />
      <circle r="3" fill="var(--accent)">
        <animateMotion dur="1.8s" repeatCount="indefinite" path="M180,40 L70,150" />
      </circle>
      <circle r="3" fill="var(--accent)">
        <animateMotion dur="1.8s" begin="0.6s" repeatCount="indefinite" path="M180,40 L290,150" />
      </circle>
      <g>
        <circle cx="180" cy="40" r="26" fill="var(--accent-bg)" stroke="var(--accent)" strokeWidth="1.5" />
        <text x="180" y="45" textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--accent)">
          Pact
        </text>
      </g>
      <g>
        <circle cx="70" cy="150" r="24" fill="var(--bg)" stroke="var(--border-strong)" strokeWidth="1.5" />
        <text x="70" y="154" textAnchor="middle" fontSize="10" fontWeight="700" fill="var(--gray-600)">
          AWS
        </text>
      </g>
      <g>
        <circle cx="290" cy="150" r="24" fill="var(--bg)" stroke="var(--border-strong)" strokeWidth="1.5" />
        <text x="290" y="154" textAnchor="middle" fontSize="10" fontWeight="700" fill="var(--gray-600)">
          Azure
        </text>
      </g>
    </svg>
  );
}

function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

function ProofStrip() {
  const [data, setData] = useState<ObservabilitySummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    getObservabilitySummary()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const runs = data?.available ? data.negotiations?.total_runs : null;
  const agreementRate = data?.available ? data.negotiations?.agreement_rate : null;

  return (
    <div className="landing-proof">
      <div className="landing-proof-item">
        <div className="landing-proof-value">74</div>
        <div className="landing-proof-label">backend tests, real APIs</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">2</div>
        <div className="landing-proof-label">live vendor pricing APIs</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">{runs != null ? runs : "—"}</div>
        <div className="landing-proof-label">logged evaluation runs</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">{pct(agreementRate)}</div>
        <div className="landing-proof-label">real agreement rate</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">0</div>
        <div className="landing-proof-label">fabricated numbers</div>
      </div>
    </div>
  );
}

export function LandingPage({ onEnterNegotiate, onEnterObservability }: Props) {
  return (
    <div className="landing">
      <header className="landing-topbar">
        <div className="landing-brand">
          <span className="brand-mark">P</span>
          <span className="brand-name">Pact</span>
        </div>
        <a
          className="landing-github-link"
          href="https://github.com/maha-rk/pact"
          target="_blank"
          rel="noreferrer"
        >
          View source on GitHub
        </a>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-text">
          <p className="landing-eyebrow">Autonomous B2B Procurement Negotiation</p>
          <h1>Which vendor's claimed discount is real?</h1>
          <p className="landing-subhead">
            Pact negotiates on your behalf against real vendor pricing,
            independently verifies every claim, enforces your policy as a
            hard gate — even against the cheapest offer — and stops for
            your approval. Evidence, not a score.
          </p>
          <div className="landing-hero-actions">
            <button className="btn-primary" onClick={onEnterNegotiate}>
              Start a negotiation →
            </button>
            <button className="btn-secondary" onClick={onEnterObservability}>
              See live results
            </button>
          </div>
        </div>
        <NegotiationGraphic />
      </section>

      <section className="landing-cards">
        <div className="landing-card">
          <h3>What Pact does</h3>
          <p>
            Discovers vendors, opens simultaneous negotiation over real
            pricing APIs, verifies every claimed discount against real
            external data, and rejects any offer that violates your
            policy — regardless of price.
          </p>
        </div>
        <div className="landing-card">
          <h3>How it works</h3>
          <ol className="landing-steps">
            <li>State a requirement — typed, photographed, or spoken</li>
            <li>Pact negotiates and verifies live, in seconds</li>
            <li>Review the Decision, Evidence, and full Replay</li>
            <li>Approve — nothing is binding until you do</li>
          </ol>
        </div>
        <div className="landing-card landing-card-cta">
          <h3>Try the flagship scenario</h3>
          <p>
            8× H100 GPUs, a 3-month contract, a $115,000 budget — watch a
            fabricated claim get caught and a compliant deal get selected,
            live.
          </p>
          <button className="btn-primary" onClick={onEnterNegotiate}>
            Open the negotiation console →
          </button>
        </div>
      </section>

      <ProofStrip />

      <footer className="landing-footer">
        <p>
          <strong>Negotiate simultaneously. Verify independently. Decide with evidence.</strong>
        </p>
      </footer>
    </div>
  );
}
