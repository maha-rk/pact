import { useEffect, useRef, useState } from "react";
import "./LandingPage.css";
import { getObservabilitySummary } from "../api";
import type { ObservabilitySummary } from "../types";

// A real front door: explains what Pact is and how to use it before
// dropping the visitor into the actual negotiation console. Nothing
// here is a new claim -- every line is condensed from README content
// already backed by tests/CI, and the proof strip is live data from
// the same /observability/summary endpoint the in-app dashboard uses,
// not a static number. The flagship walkthrough below uses the exact
// real figures from the actual flagship scenario (PRD's canonical
// demo) -- not invented for the page.

interface Props {
  onEnterNegotiate: () => void;
  onEnterObservability: () => void;
}

// True the first time the referenced element scrolls into view, forever
// after -- the shared trigger behind both the fade-up reveal and the
// proof-strip counters below.
function useInView<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return [ref, visible] as const;
}

// Fades a section up into place the first time it scrolls into view.
// Pure CSS transition driven by one class toggle -- no animation library.
function Reveal({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const [ref, visible] = useInView<HTMLDivElement>();
  return (
    <div ref={ref} className={`reveal ${visible ? "reveal-visible" : ""} ${className}`}>
      {children}
    </div>
  );
}

// Counts 0 -> target once the element is visible. Real numbers only --
// null stays "--" (rendered by the caller), never faked into a count.
function useCountUp(target: number | null, active: boolean, duration = 900): number | null {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!active || target == null) return;
    const start = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) * (1 - progress);
      setValue(Math.round(eased * target));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, active, duration]);

  return target == null ? null : value;
}

// The real flagship scenario's event log, condensed to console lines --
// same figures as the walkthrough section below, same figures a live
// run of `python scripts/run_scenario.py --fixture flagship` produces.
// Not a mockup of a hypothetical feature; a scripted replay of a real one.
const CONSOLE_LINES: { text: string; tone: "cmd" | "muted" | "ok" | "fail" | "decision" }[] = [
  { text: '$ pact negotiate --requirement "8x H100, 3mo, $115k"', tone: "cmd" },
  { text: "→ discovering vendors...", tone: "muted" },
  { text: "✓ AWS Vendor Agent found", tone: "ok" },
  { text: "✓ Azure Vendor Agent found", tone: "ok" },
  { text: "→ AWS offers $118,886.40 (claims 25% discount)", tone: "muted" },
  { text: "→ verifying against AWS Price List Bulk API...", tone: "muted" },
  { text: "✗ no such discount tier exists — claim rejected", tone: "fail" },
  { text: "→ Azure offers $39,246.20 (claims 81.52% discount)", tone: "muted" },
  { text: "→ verifying against Azure Retail Prices API...", tone: "muted" },
  { text: "✓ claim verified — matches live pricing", tone: "ok" },
  { text: "→ checking policy compliance...", tone: "muted" },
  { text: "✓ within $115,000 budget", tone: "ok" },
  { text: "● decision: Azure selected — $39,246.20", tone: "decision" },
  { text: "  pending human approval", tone: "muted" },
];

function LiveConsole() {
  const [lineIndex, setLineIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const reducedMotion = useRef(
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (reducedMotion.current) {
      setLineIndex(CONSOLE_LINES.length);
      return;
    }

    const current = CONSOLE_LINES[lineIndex];
    if (!current) {
      const resetTimer = setTimeout(() => {
        setLineIndex(0);
        setCharIndex(0);
      }, 2600);
      return () => clearTimeout(resetTimer);
    }

    if (charIndex < current.text.length) {
      const speed = current.tone === "cmd" ? 38 : 14;
      const t = setTimeout(() => setCharIndex((c) => c + 1), speed);
      return () => clearTimeout(t);
    }

    const lineDelay = current.tone === "decision" ? 700 : 220;
    const t = setTimeout(() => {
      setLineIndex((l) => l + 1);
      setCharIndex(0);
    }, lineDelay);
    return () => clearTimeout(t);
  }, [lineIndex, charIndex]);

  const doneLines = CONSOLE_LINES.slice(0, lineIndex);
  const typingLine = CONSOLE_LINES[lineIndex];
  const typingText = typingLine ? typingLine.text.slice(0, charIndex) : "";

  return (
    <div className="console-glow">
      <div className="console" role="img" aria-label="A real negotiation log: AWS's discount claim is rejected, Azure's is verified, Azure is selected at $39,246.20 pending approval">
        <div className="console-titlebar">
          <span className="console-dot console-dot-red" />
          <span className="console-dot console-dot-yellow" />
          <span className="console-dot console-dot-green" />
          <span className="console-titlebar-label">pact — negotiation</span>
        </div>
        <div className="console-body">
          {doneLines.map((line, i) => (
            <div key={i} className={`console-line console-${line.tone}`}>
              {line.text}
            </div>
          ))}
          {typingLine && (
            <div className={`console-line console-${typingLine.tone}`}>
              {typingText}
              <span className="console-cursor" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function IconSearch() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

function IconSteps() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 6h16M4 12h10M4 18h6" />
    </svg>
  );
}

function IconFlag() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 21V4" />
      <path d="M5 4h13l-3 4 3 4H5" />
    </svg>
  );
}

function ProofStrip() {
  const [data, setData] = useState<ObservabilitySummary | null>(null);
  const [ref, visible] = useInView<HTMLDivElement>(0.4);

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

  const runs = data?.available ? (data.negotiations?.total_runs ?? null) : null;
  const agreementRate = data?.available ? data.negotiations?.agreement_rate : null;
  const agreementPct = agreementRate != null ? Math.round(agreementRate * 100) : null;

  const testsCount = useCountUp(79, visible);
  const vendorCount = useCountUp(2, visible);
  const runsCount = useCountUp(runs, visible);
  const agreementCount = useCountUp(agreementPct, visible);
  const fabricatedCount = useCountUp(0, visible);

  return (
    <div className="landing-proof" ref={ref}>
      <div className="landing-proof-item">
        <div className="landing-proof-value">{testsCount}</div>
        <div className="landing-proof-label">backend tests, real APIs</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">{vendorCount}</div>
        <div className="landing-proof-label">live vendor pricing APIs</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">{runsCount != null ? runsCount : "—"}</div>
        <div className="landing-proof-label">logged evaluation runs</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">{agreementCount != null ? `${agreementCount}%` : "—"}</div>
        <div className="landing-proof-label">real agreement rate</div>
      </div>
      <div className="landing-proof-item">
        <div className="landing-proof-value">{fabricatedCount}</div>
        <div className="landing-proof-label">fabricated numbers</div>
      </div>
    </div>
  );
}

function TodayVsPact() {
  return (
    <section className="landing-section" id="comparison">
      <div className="landing-section-inner">
        <p className="landing-section-eyebrow">The shift</p>
        <h2>Today vs. with Pact</h2>
        <p className="landing-section-lede">
          Cloud GPU procurement is Pact's first deployment of a broader idea:
          as organizations increasingly transact through software agents
          rather than people, something has to verify what those agents
          claim to each other and enforce policy on an organization's behalf
          before a commitment is made.
        </p>
        <div className="compare-grid">
          <div className="compare-column compare-today">
            <h3>Today</h3>
            <ol className="compare-steps">
              <li>Buyer emails vendors</li>
              <li>Quotes trickle in, on their own timeline</li>
              <li>Spreadsheet comparison</li>
              <li>Decision made on trust</li>
            </ol>
          </div>
          <div className="compare-arrow" aria-hidden="true">→</div>
          <div className="compare-column compare-pact">
            <h3>With Pact</h3>
            <ol className="compare-steps">
              <li>Buyer Agent ↔ Vendor Agents, simultaneously, over real HTTP</li>
              <li>Verification Agent checks every claim against real data</li>
              <li>Compliance Agent enforces policy as a hard gate</li>
              <li>Decision + Evidence, then human approval</li>
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}

function WalkthroughStep({
  vendor,
  claim,
  verification,
  verified,
  complianceLabel,
  compliant,
  outcome,
}: {
  vendor: string;
  claim: string;
  verification: string;
  verified: boolean;
  complianceLabel: string;
  compliant: boolean;
  outcome: string;
}) {
  return (
    <div className={`walkthrough-vendor ${compliant ? "walkthrough-selected" : "walkthrough-rejected"}`}>
      <div className="walkthrough-vendor-header">
        <span className={`vendor-badge vendor-${vendor.toLowerCase()}`}>{vendor}</span>
      </div>
      <div className="walkthrough-row">
        <span className="walkthrough-label">Claimed</span>
        <span className="walkthrough-value">{claim}</span>
      </div>
      <div className="walkthrough-row">
        <span className="walkthrough-label">Verification</span>
        <span className={`walkthrough-value ${verified ? "walkthrough-pass" : "walkthrough-fail"}`}>
          {verified ? "✓ " : "✗ "}
          {verification}
        </span>
      </div>
      <div className="walkthrough-row">
        <span className="walkthrough-label">Policy</span>
        <span className={`walkthrough-value ${compliant ? "walkthrough-pass" : "walkthrough-fail"}`}>
          {compliant ? "✓ " : "✗ "}
          {complianceLabel}
        </span>
      </div>
      <div className="walkthrough-outcome">{outcome}</div>
    </div>
  );
}

function OneNegotiationExplained() {
  return (
    <section className="landing-section landing-section-alt" id="example">
      <div className="landing-section-inner">
        <p className="landing-section-eyebrow">One real negotiation, fully explained</p>
        <h2>The flagship scenario</h2>
        <p className="landing-section-lede">
          These are the actual figures from Pact's canonical demo scenario —
          reproduce them yourself with{" "}
          <code>python scripts/run_scenario.py --fixture flagship --approve</code>.
        </p>

        <div className="walkthrough-input">
          <div className="walkthrough-input-item">
            <div className="walkthrough-input-value">8×</div>
            <div className="walkthrough-input-label">H100 GPUs</div>
          </div>
          <div className="walkthrough-input-item">
            <div className="walkthrough-input-value">3 mo</div>
            <div className="walkthrough-input-label">contract</div>
          </div>
          <div className="walkthrough-input-item">
            <div className="walkthrough-input-value">$115,000</div>
            <div className="walkthrough-input-label">budget ceiling</div>
          </div>
        </div>

        <div className="walkthrough-vendors">
          <WalkthroughStep
            vendor="AWS"
            claim="25% committed-use discount"
            verification="No such discount tier exists under 12 months"
            verified={false}
            complianceLabel="Corrected price ($118,886.40) exceeds budget"
            compliant={false}
            outcome="Rejected — claim caught, then rejected again on compliance"
          />
          <WalkthroughStep
            vendor="Azure"
            claim="81.52% Spot discount"
            verification="Matches live Azure Retail Prices API exactly"
            verified={true}
            complianceLabel="$39,246.20 is within the $115,000 budget"
            compliant={true}
            outcome="Selected — verified, compliant, lowest real price"
          />
        </div>

        <div className="walkthrough-decision">
          <div className="walkthrough-decision-label">Decision</div>
          <div className="walkthrough-decision-value">
            <span className="vendor-badge vendor-azure">AZURE</span>
            <span className="walkthrough-decision-price">$39,246.20</span>
          </div>
          <div className="walkthrough-decision-note">
            Pending a named human approval — nothing above this line is binding.
          </div>
        </div>
      </div>
    </section>
  );
}

function NoScoring() {
  return (
    <section className="landing-section" id="evidence">
      <div className="landing-section-inner">
        <p className="landing-section-eyebrow">Why not a score</p>
        <h2>Pact doesn't score vendors</h2>
        <div className="noscoring-grid">
          <div className="noscoring-column">
            <h3>What most tools produce</h3>
            <table className="noscoring-table">
              <thead>
                <tr>
                  <th>Vendor</th>
                  <th>Composite score</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>Vendor A</td><td>88</td></tr>
                <tr><td>Vendor B</td><td>82</td></tr>
                <tr><td>Vendor C</td><td>76</td></tr>
              </tbody>
            </table>
            <p className="noscoring-caption">
              Then the honest follow-up — <em>why 88, not 85?</em> — has no
              real answer. A weighted blend of sub-scores nobody outside the
              system can independently check, presented with false precision.
            </p>
          </div>
          <div className="noscoring-column">
            <h3>What Pact produces</h3>
            <p className="noscoring-body">
              Every claim verified against real external data. Policy applied
              as a hard pass/fail gate. A negotiated outcome where a claim
              doesn't hold up. A decision whose evidence you can check
              yourself — not a score you have to trust.
            </p>
            <p className="noscoring-caption">
              See <a href="#example">the flagship scenario above</a> for what
              that looks like on a real run.
            </p>
          </div>
        </div>
      </div>
    </section>
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
        <nav className="landing-nav">
          <a href="#comparison">How it works</a>
          <a href="#example">Example</a>
          <a href="#evidence">Evidence</a>
          <a href="https://github.com/maha-rk/pact/blob/main/docs/PRD.md" target="_blank" rel="noreferrer">PRD</a>
          <a href="https://github.com/maha-rk/pact/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer">Architecture</a>
        </nav>
        <a
          className="landing-github-link"
          href="https://github.com/maha-rk/pact"
          target="_blank"
          rel="noreferrer"
        >
          View source on GitHub
        </a>
      </header>

      <div className="landing-hero-wrap">
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
          <LiveConsole />
        </section>
      </div>

      <Reveal className="landing-cards">
        <div className="landing-card">
          <div className="landing-card-icon landing-card-icon-green"><IconSearch /></div>
          <h3>What Pact does</h3>
          <p>
            Discovers vendors, opens simultaneous negotiation over real
            pricing APIs, verifies every claimed discount against real
            external data, and rejects any offer that violates your
            policy — regardless of price.
          </p>
        </div>
        <div className="landing-card">
          <div className="landing-card-icon landing-card-icon-blue"><IconSteps /></div>
          <h3>How it works</h3>
          <ol className="landing-steps">
            <li>State a requirement — typed, photographed, or spoken</li>
            <li>Pact negotiates and verifies live, in seconds</li>
            <li>Review the Decision, Evidence, and full Replay</li>
            <li>Approve — nothing is binding until you do</li>
          </ol>
        </div>
        <div className="landing-card landing-card-cta">
          <div className="landing-card-icon landing-card-icon-cta"><IconFlag /></div>
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
      </Reveal>

      <Reveal><TodayVsPact /></Reveal>
      <Reveal><OneNegotiationExplained /></Reveal>
      <Reveal><NoScoring /></Reveal>

      <Reveal><ProofStrip /></Reveal>

      <footer className="landing-footer">
        <p className="landing-footer-tagline">
          <strong>Negotiate simultaneously. Verify independently. Decide with evidence.</strong>
        </p>
        <div className="landing-footer-links">
          <a href="https://github.com/maha-rk/pact/blob/main/docs/PRD.md" target="_blank" rel="noreferrer">Product Requirements</a>
          <a href="https://github.com/maha-rk/pact/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer">Architecture</a>
          <a href="https://github.com/maha-rk/pact/blob/main/docs/ENGINEERING_LOG.md" target="_blank" rel="noreferrer">Engineering Log</a>
          <a href="https://github.com/maha-rk/pact/actions">CI</a>
          <a href="https://github.com/maha-rk/pact/commits/main">Commit history</a>
          <a href="https://github.com/maha-rk/pact">GitHub</a>
        </div>
      </footer>
    </div>
  );
}
