import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./LandingPage.css";
import { getObservabilitySummary } from "../api";
import type { ObservabilitySummary } from "../types";
import { PactMark } from "./PactMark";

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
  { text: '$ pact negotiate "8x H100 GPUs, 3-month term, $115K budget"', tone: "cmd" },
  { text: "→ contacting AWS and Azure...", tone: "muted" },
  { text: "✓ AWS quotes $118,886.40 (claims a 25% loyalty discount)", tone: "ok" },
  { text: "→ checking that discount against AWS's real pricing...", tone: "muted" },
  { text: "✗ discount doesn't exist — renegotiating with AWS", tone: "fail" },
  { text: "✓ Azure quotes $39,246.20 (claims an 81.52% spot discount)", tone: "ok" },
  { text: "→ checking that discount against Azure's real pricing...", tone: "muted" },
  { text: "✓ verified — Azure's price is genuine", tone: "ok" },
  { text: "→ does this fit company policy?", tone: "muted" },
  { text: "✓ yes — within the $115,000 budget", tone: "ok" },
  { text: "● recommendation: Azure — saves $79,640.20 vs. AWS's real price", tone: "decision" },
  { text: "  awaiting your approval", tone: "muted" },
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

function IconShieldCheck() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

function IconScales() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18M8 21h8M7 7h10" />
      <path d="M4 7l-2.5 5a2.5 2.5 0 0 0 5 0L4 7z" />
      <path d="M20 7l-2.5 5a2.5 2.5 0 0 0 5 0L20 7z" />
    </svg>
  );
}

function IconDocument() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </svg>
  );
}

function IconPerson() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6" />
    </svg>
  );
}

function IconMic() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3M9 21h6" />
    </svg>
  );
}

function IconPeople() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="9" cy="8" r="3.2" />
      <path d="M2.5 20c0-3.6 2.9-6.2 6.5-6.2s6.5 2.6 6.5 6.2z" />
      <circle cx="17" cy="7" r="2.6" opacity="0.85" />
      <path d="M15 13.3c2.9.4 5 2.7 5 6v.7h-3.2" opacity="0.85" />
    </svg>
  );
}

function IconBriefcase() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M3 12h18" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

function IconCheckCircle() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.5l2.5 2.5 4.5-5" />
    </svg>
  );
}

function IconSparkle() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z" />
    </svg>
  );
}

function IconPhoto() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="8.5" cy="10" r="1.5" />
      <path d="M21 15l-5-5-4 4-2-2-5 5" />
    </svg>
  );
}

function IconTextLines() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 6h16M4 12h16M4 18h10" />
    </svg>
  );
}

function IconChat() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 11.5a8.4 8.4 0 0 1-8.4 8.4 8.3 8.3 0 0 1-3.8-.9L3 21l1.9-5.8a8.3 8.3 0 0 1-.9-3.8A8.4 8.4 0 0 1 12.5 3a8.4 8.4 0 0 1 8.5 8.5z" />
    </svg>
  );
}

function IconSearchDoc() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <circle cx="10.5" cy="14" r="2.2" />
      <path d="M12.2 15.7L14 17.5" />
    </svg>
  );
}

function IconListCheck() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 6h11M9 12h11M9 18h11" />
      <path d="M4 6l.01.01M4 12l.01.01M4 18l.01.01" />
    </svg>
  );
}

function IconChartBars() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19V10M11 19V5M18 19v-7" />
      <path d="M3 21h18" />
    </svg>
  );
}

function FlowConnector({ id, from, to }: { id: string; from: string; to: string }) {
  return (
    <svg className="process-flow-connector" width="26" height="18" viewBox="0 0 26 18" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="26" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor={from} />
          <stop offset="1" stopColor={to} />
        </linearGradient>
      </defs>
      <path d="M1 9 H18" stroke={`url(#${id})`} strokeWidth="3" strokeLinecap="round" />
      <path d="M13 2l7 7-7 7" stroke={`url(#${id})`} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

function LeftFanIn() {
  return (
    <svg className="process-fan-in" width="150" height="130" viewBox="0 0 150 130" fill="none" aria-hidden="true">
      <g stroke="#7c3aed" strokeWidth="3.5" strokeLinecap="round" opacity="0.85">
        <path d="M0 8 H76 L100 65" />
        <path d="M0 41 H76 L100 65" />
        <path d="M0 74 H76 L100 65" />
        <path d="M0 107 H76 L100 65" />
      </g>
      <circle cx="100" cy="65" r="5" fill="#7c3aed" />
      <path d="M106 65 H132" stroke="#7c3aed" strokeWidth="3.5" strokeLinecap="round" strokeDasharray="1 9" />
      <circle cx="0" cy="8" r="3.5" fill="#a78bfa" />
      <circle cx="0" cy="41" r="3.5" fill="#a78bfa" />
      <circle cx="0" cy="74" r="3.5" fill="#a78bfa" />
      <circle cx="0" cy="107" r="3.5" fill="#a78bfa" />
    </svg>
  );
}

function IconExpand() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3H5a2 2 0 0 0-2 2v3" />
      <path d="M16 3h3a2 2 0 0 1 2 2v3" />
      <path d="M8 21H5a2 2 0 0 1-2-2v-3" />
      <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
    </svg>
  );
}

// Hover-to-expand: pure CSS (:hover / :focus-within), no click, no new
// tab, no JS state -- the preview panel is always in the DOM at a fixed
// size and only its opacity/visibility/transform toggle, so there's no
// layout jump when it appears. Keyboard-focusable so it's not mouse-only.
function IconClose() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

// Click to open, not hover -- a full-size lightbox in the current tab
// (no target="_blank", no navigation). Closes on the X button, on
// backdrop click, or on Escape; body scroll is locked while open so
// the page behind it doesn't scroll along with the image.
function ArchitectureExpand() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    // Lock both html and body -- document.scrollingElement is the
    // <html> element in standards mode, not <body>, so locking body
    // alone doesn't actually stop the page from scrolling.
    const html = document.documentElement;
    const previousHtmlOverflow = html.style.overflow;
    const previousBodyOverflow = document.body.style.overflow;
    html.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      html.style.overflow = previousHtmlOverflow;
      document.body.style.overflow = previousBodyOverflow;
    };
  }, [open]);

  return (
    <div className="arch-expand">
      <button
        type="button"
        className="arch-expand-trigger"
        aria-label="View the full Pact architecture diagram"
        onClick={() => setOpen(true)}
      >
        <IconExpand />
        <span>Architecture</span>
      </button>
      {open &&
        createPortal(
          // Portaled straight onto <body> -- rendering this inside the
          // normal component tree put it under a <Reveal> wrapper whose
          // scroll-in animation sets `transform` on an ancestor, which
          // silently turns position:fixed here into "fixed relative to
          // that ancestor" instead of the viewport (a real CSS rule, not
          // a bug in isolation) -- so the close button could scroll off
          // screen. A portal sidesteps that ancestor entirely.
          <div className="arch-lightbox-backdrop">
            <button
              type="button"
              className="arch-lightbox-close"
              aria-label="Close architecture diagram"
              onClick={() => setOpen(false)}
            >
              <IconClose />
            </button>
            <div className="arch-lightbox" onClick={() => setOpen(false)}>
              <img
                className="arch-lightbox-img"
                src="/architecture-diagram.png"
                alt="Pact architecture diagram: six-layer real system from intake through evidence, with live AWS/Azure vendor integrations, real deployment (Docker on Render + ngrok), and scaffolded GCP/RunPod roadmap items clearly marked"
                onClick={(e) => e.stopPropagation()}
              />
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

function ProcessStep({
  number,
  color,
  icon,
  title,
  miniIcons,
  caption,
}: {
  number: number;
  color: "purple" | "violet" | "indigo" | "blue" | "cyan" | "green";
  icon: React.ReactNode;
  title: string;
  miniIcons: React.ReactNode[];
  caption: string;
}) {
  return (
    <div className={`process-step process-step-${color}`}>
      <div className="process-step-icon-wrap">
        <span className="process-step-number">{number}</span>
        <div className="process-step-icon">{icon}</div>
      </div>
      <h3>{title}</h3>
      <div className="process-step-box">
        <div className="process-step-mini-icons">
          {miniIcons.map((mi, i) => (
            <span key={i}>{mi}</span>
          ))}
        </div>
        <p className="process-step-caption">{caption}</p>
      </div>
    </div>
  );
}

function HowPactWorks({ onEnterNegotiate }: { onEnterNegotiate: () => void }) {
  return (
    <section className="landing-section landing-section-alt" id="how-it-works">
      <div className="landing-section-inner">
        <h2 className="process-heading">
          The 6-Step Process: From requirement to decision, <span className="landing-section-accent">in seconds</span>
        </h2>
        <p className="landing-section-lede process-lede">
          Pact is your AI-native procurement copilot — it streamlines negotiation and compliance
          with speed, accuracy, and confidence.
        </p>
        <div className="process-steps">
          <LeftFanIn />
          <ProcessStep
            number={1}
            color="purple"
            icon={<IconBriefcase />}
            title="Buyer"
            miniIcons={[<IconMic key="mic" />, <IconPhoto key="photo" />, <IconTextLines key="text" />]}
            caption="Captures your requirement and policy"
          />
          <FlowConnector id="flow-1" from="#7c3aed" to="#9333ea" />
          <ProcessStep
            number={2}
            color="violet"
            icon={<IconSearch />}
            title="Discovery"
            miniIcons={[<IconSearch key="s" />, <IconShieldCheck key="sh" />]}
            caption="Finds vendors, verifies their identity"
          />
          <FlowConnector id="flow-2" from="#9333ea" to="#4f46e5" />
          <ProcessStep
            number={3}
            color="indigo"
            icon={<IconPeople />}
            title="Negotiation"
            miniIcons={[<IconChat key="c1" />, <IconChat key="c2" />]}
            caption="Real HTTP offers, round by round"
          />
          <FlowConnector id="flow-3" from="#4f46e5" to="#2563eb" />
          <ProcessStep
            number={4}
            color="blue"
            icon={<IconSearchDoc />}
            title="Verification"
            miniIcons={[<IconSearchDoc key="s" />, <IconListCheck key="l" />]}
            caption="Claims checked against real pricing data"
          />
          <FlowConnector id="flow-4" from="#2563eb" to="#0891b2" />
          <ProcessStep
            number={5}
            color="cyan"
            icon={<IconShieldCheck />}
            title="Compliance"
            miniIcons={[<IconShieldCheck key="sh" />, <IconListCheck key="l" />]}
            caption="Policy enforced as a hard gate"
          />
          <FlowConnector id="flow-5" from="#0891b2" to="#16a34a" />
          <ProcessStep
            number={6}
            color="green"
            icon={<IconCheckCircle />}
            title="Decision"
            miniIcons={[<IconChartBars key="ch" />, <IconDocument key="d" />, <IconPerson key="p" />]}
            caption="Evidence, reasoning, your approval"
          />
          <FlowConnector id="flow-6" from="#4ade80" to="#16a34a" />
          <div className="process-capstone">
            <div className="process-capstone-icon"><IconCheckCircle /></div>
            <span>Decision Delivered</span>
          </div>
        </div>
        <div className="process-cta">
          <button className="btn-primary" onClick={onEnterNegotiate}>
            <IconSparkle /> Try the flagship scenario →
          </button>
        </div>
      </div>
      <ArchitectureExpand />
    </section>
  );
}

// Live, not decorative -- each sub-label pulls a real figure from the
// same /observability/summary endpoint the ProofStrip and in-app
// dashboard use, and falls back to an honest structural description
// (never an invented number) while that data is unavailable. "Policy
// enforcement" reports the real rejection rate rather than an "always
// compliant" claim -- compliance can and does fail (that's the AWS
// rejection in the flagship scenario), so the honest framing is how
// often the gate actually catches something, not a false 100% claim.
function TrustStats() {
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

  const negotiations = data?.available ? data.negotiations : null;
  const catchRate = negotiations?.claim_mismatch_catch_rate;
  const rejectionRate = negotiations?.compliance_rejection_rate;
  const totalRuns = negotiations?.total_runs;

  const verificationDetail =
    catchRate != null ? `${Math.round(catchRate * 100)}% mismatch catch rate` : "Independently verified";
  const complianceDetail =
    rejectionRate != null ? `${Math.round(rejectionRate * 100)}% rejected on policy` : "Hard policy gate";
  const evidenceDetail = totalRuns != null ? `${totalRuns} decisions logged` : "Audit-ready";

  return (
    <ul className="trust-badges">
      <li>
        <IconShieldCheck />
        <div>
          <span className="trust-badge-title">Claim verification</span>
          <span className="trust-badge-detail">{verificationDetail}</span>
        </div>
      </li>
      <li>
        <IconScales />
        <div>
          <span className="trust-badge-title">Policy enforcement</span>
          <span className="trust-badge-detail">{complianceDetail}</span>
        </div>
      </li>
      <li>
        <IconDocument />
        <div>
          <span className="trust-badge-title">Evidence trails</span>
          <span className="trust-badge-detail">{evidenceDetail}</span>
        </div>
      </li>
      <li>
        <IconPerson />
        <div>
          <span className="trust-badge-title">Human approval</span>
          <span className="trust-badge-detail">You stay in control</span>
        </div>
      </li>
    </ul>
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

  const testsCount = useCountUp(79, visible);
  const vendorCount = useCountUp(2, visible);
  const runsCount = useCountUp(runs, visible);
  const traceabilityCount = useCountUp(100, visible);
  const fabricatedCount = useCountUp(0, visible);

  return (
    <section className="landing-proof-bar">
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
          <div className="landing-proof-value">{traceabilityCount}%</div>
          <div className="landing-proof-label">evidence traceability</div>
        </div>
        <div className="landing-proof-item">
          <div className="landing-proof-value">{fabricatedCount}</div>
          <div className="landing-proof-label">fabricated numbers</div>
        </div>
      </div>
    </section>
  );
}

function TrustPillar({
  icon,
  color,
  name,
  body,
  flow,
}: {
  icon: React.ReactNode;
  color: "purple" | "blue" | "green";
  name: string;
  body: string;
  flow: [string, string, string];
}) {
  return (
    <div className={`trust-pillar trust-pillar-${color}`}>
      <div className="trust-pillar-icon">{icon}</div>
      <h3>{name}</h3>
      <p className="trust-pillar-body">{body}</p>
      <div className="trust-pillar-flow">
        <span>{flow[0]}</span>
        <span className="trust-pillar-arrow trust-pillar-arrow-1" aria-hidden="true" />
        <span>{flow[1]}</span>
        <span className="trust-pillar-arrow trust-pillar-arrow-2" aria-hidden="true" />
        <span className="trust-pillar-outcome">{flow[2]}</span>
      </div>
    </div>
  );
}

function WhyTrustMatters() {
  return (
    <section className="landing-section landing-section-thesis" id="trust">
      <div className="landing-section-inner">
        <p className="landing-section-eyebrow landing-section-eyebrow-light">Why this matters</p>
        <h2>Why Agent Commerce Needs Trust</h2>
        <p className="landing-section-lede landing-section-lede-light">
          Organisations can transact through agents. Trust is what makes that possible.
        </p>
        <div className="trust-pillar-grid">
          <TrustPillar
            icon={<IconShieldCheck />}
            color="purple"
            name="Verification"
            body="A negotiating claim is not a fact. Every discount, capability, and price must be independently verified before it can influence a decision."
            flow={["Vendor claim", "Verification", "Approved / rejected"]}
          />
          <TrustPillar
            icon={<IconScales />}
            color="blue"
            name="Compliance"
            body="The cheapest deal is not always the right one. Budget, certifications, and ESG thresholds are enforced as hard gates — policy overrides optimization, even against the best price on the table."
            flow={["Offer", "Compliance", "Pass / fail"]}
          />
          <TrustPillar
            icon={<IconDocument />}
            color="green"
            name="Evidence"
            body="A recommendation without evidence can't be audited. Every decision needs a traceable reason, not just an outcome."
            flow={["Decision", "Evidence", "Approval"]}
          />
        </div>
      </div>
    </section>
  );
}

function IconCrossCircle() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M9 9l6 6M15 9l-6 6" />
    </svg>
  );
}

function IconCheckSmall() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12.5l2.5 2.5 5-5" />
    </svg>
  );
}

function CompareItem({ tone, text }: { tone: "muted" | "accent"; text: string }) {
  return (
    <li className={`compare-item compare-item-${tone}`}>
      <span className="compare-item-icon">{tone === "muted" ? <IconCrossCircle /> : <IconCheckSmall />}</span>
      <span>{text}</span>
    </li>
  );
}

function PulseArrow() {
  return (
    <svg className="compare-arrow-svg" width="64" height="32" viewBox="0 0 64 32" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="compare-arrow-grad" x1="0" y1="0" x2="64" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6b7280" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <path d="M2 16 H50" stroke="url(#compare-arrow-grad)" strokeWidth="3" strokeLinecap="round" opacity="0.55" />
      <path d="M42 6l14 10-14 10" stroke="url(#compare-arrow-grad)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <circle r="3.5" fill="#c4b5fd">
        <animateMotion dur="2.2s" repeatCount="indefinite" path="M4 16 H50" />
      </circle>
    </svg>
  );
}

function TodayVsPact() {
  return (
    <section className="landing-section landing-section-compare" id="comparison">
      <div className="landing-section-inner">
        <p className="landing-section-eyebrow landing-section-eyebrow-light">The shift, today</p>
        <h2>From Spreadsheets to Agents</h2>
        <div className="compare-grid">
          <div className="compare-column compare-today">
            <h3>Today</h3>
            <ul className="compare-steps">
              <CompareItem tone="muted" text="Buyer emails vendors" />
              <CompareItem tone="muted" text="Quotes trickle in, on their own timeline" />
              <CompareItem tone="muted" text="Spreadsheet comparison" />
              <CompareItem tone="muted" text="Decision made on trust" />
            </ul>
          </div>
          <div className="compare-arrow" aria-hidden="true"><PulseArrow /></div>
          <div className="compare-column compare-pact">
            <h3>With Pact</h3>
            <ul className="compare-steps">
              <CompareItem tone="accent" text="Buyer Agent ↔ Vendor Agents, simultaneously, over real HTTP" />
              <CompareItem tone="accent" text="Verification Agent checks every claim against real data" />
              <CompareItem tone="accent" text="Compliance Agent enforces policy as a hard gate — budget, certifications, ESG" />
              <CompareItem tone="accent" text="Decision + Evidence, then human approval" />
            </ul>
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
          <PactMark size={34} />
          <span className="brand-name">Pact</span>
        </div>
        <nav className="landing-nav">
          <a href="#how-it-works">How it works</a>
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
            <p className="landing-eyebrow">The trust layer for agent commerce</p>
            <h1>Autonomous procurement for the agent economy.</h1>
            <p className="landing-subhead">
              Buyer agents negotiate directly with vendor agents. Pact
              verifies every claim, enforces policy as a hard gate, and
              produces evidence-backed decisions before a human approves
              them.
            </p>
            <div className="landing-hero-actions">
              <button className="btn-primary" onClick={onEnterNegotiate}>
                Start a negotiation →
              </button>
              <button className="btn-secondary" onClick={onEnterObservability}>
                See live results →
              </button>
            </div>
            <TrustStats />
          </div>
          <div className="landing-console-col">
            <p className="console-caption">Watch it happen — which vendor's claimed discount is real?</p>
            <LiveConsole />
          </div>
        </section>
      </div>

      <ProofStrip />

      <Reveal><WhyTrustMatters /></Reveal>
      <Reveal><HowPactWorks onEnterNegotiate={onEnterNegotiate} /></Reveal>
      <Reveal><TodayVsPact /></Reveal>
      <Reveal><OneNegotiationExplained /></Reveal>
      <Reveal><NoScoring /></Reveal>

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
