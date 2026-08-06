import type { NegotiationEvent, NegotiationState } from "../types";

// PRD §22 / FR-10: a chronological, timestamped view of one completed
// run -- every offer, every verification/compliance check and result,
// any renegotiation triggered. Built from the same audit package as
// DecisionView -- two projections of one real record, not two sources.

const EVENT_LABELS: Record<string, string> = {
  requirement_received: "Requirement received",
  vendor_discovered: "Vendor discovered",
  offer_made: "Offer made",
  claim_verified: "Claim verified",
  claim_rejected: "Claim rejected",
  renegotiation_triggered: "Renegotiation triggered",
  compliance_passed: "Compliance passed",
  compliance_rejected: "Compliance rejected",
  decision_produced: "Decision produced",
  decision_approved: "Decision approved",
  no_compliant_deal: "No compliant deal",
  vendor_unavailable: "Vendor unavailable",
  narration_degraded: "Narration degraded (Gemini)",
  plausibility_screened: "Plausibility pre-screen (Gemma)",
};

const EVENT_CLASS: Record<string, string> = {
  claim_rejected: "event-negative",
  compliance_rejected: "event-negative",
  no_compliant_deal: "event-negative",
  vendor_unavailable: "event-negative",
  narration_degraded: "event-negative",
  claim_verified: "event-positive",
  compliance_passed: "event-positive",
  decision_produced: "event-highlight",
  decision_approved: "event-highlight",
  plausibility_screened: "event-muted",
};

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString(undefined, { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function EventRow({ event }: { event: NegotiationEvent }) {
  const cls = EVENT_CLASS[event.event_type] ?? "";
  return (
    <li className={`timeline-event ${cls}`}>
      <span className="timeline-time">{formatTime(event.timestamp)}</span>
      {event.vendor_id && <span className={`vendor-badge vendor-${event.vendor_id} small`}>{event.vendor_id.toUpperCase()}</span>}
      {event.round_number != null && <span className="round-badge">R{event.round_number}</span>}
      <span className="timeline-label">{EVENT_LABELS[event.event_type] ?? event.event_type}</span>
      <span className="timeline-detail">{event.detail}</span>
      {event.chain_hash && (
        <code className="timeline-chain-hash" title={`Audit chain hash: ${event.chain_hash}`}>
          {event.chain_hash.slice(0, 8)}
        </code>
      )}
    </li>
  );
}

export function ReplayTimeline({ state }: { state: NegotiationState }) {
  const chainHead = state.events.length > 0 ? state.events[state.events.length - 1].chain_hash : null;
  return (
    <div className="replay-timeline">
      {chainHead && (
        <p className="chain-head-note">
          Every event above is individually hash-chained to the one before it —
          tampering with any single event, at any point in this list, changes
          every chain hash after it. Current chain head:{" "}
          <code title={chainHead}>{chainHead.slice(0, 12)}…</code>
        </p>
      )}
      <ul>
        {state.events.map((event, i) => (
          <EventRow key={i} event={event} />
        ))}
      </ul>
    </div>
  );
}
