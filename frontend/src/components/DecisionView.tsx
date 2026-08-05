import { useState } from "react";
import type { NegotiationState } from "../types";
import { approveNegotiation } from "../api";

// PRD §22 "Key UI Surfaces": the recommended vendor and final terms, each
// evidence item individually attributed to its real source, the
// reasoning statement, and human approval as the only way to finalize.

interface Props {
  state: NegotiationState;
  onUpdated: (updated: NegotiationState) => void;
}

export function DecisionView({ state, onUpdated }: Props) {
  const [approving, setApproving] = useState(false);
  const [approver, setApprover] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { decision, status } = state;

  if (status === "no_compliant_deal") {
    return (
      <div className="decision-view no-deal">
        <h3>No compliant deal found</h3>
        <p>
          No vendor produced an offer that passed both the verification and
          compliance gates within the negotiation round limit. Reported
          honestly, not forced through (PRD §27).
        </p>
      </div>
    );
  }

  if (!decision) {
    return <div className="decision-view">Negotiation still in progress...</div>;
  }

  const handleApprove = async () => {
    if (!approver.trim()) {
      setError("Enter an approver name first.");
      return;
    }
    setApproving(true);
    setError(null);
    try {
      const updated = await approveNegotiation(state.negotiation_id, approver.trim());
      onUpdated(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="decision-view">
      <div className="decision-header">
        <span className={`vendor-badge vendor-${decision.selected_vendor}`}>
          {decision.selected_vendor?.toUpperCase()}
        </span>
        <span className="final-price">
          ${decision.final_price_usd?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
        </span>
      </div>

      <h4>Evidence</h4>
      <ul className="evidence-list">
        {decision.evidence.map((item, i) => (
          <li key={i}>
            <strong>{item.label}:</strong> {item.value}
            <div className="evidence-source">source: {item.source}</div>
          </li>
        ))}
      </ul>

      <h4>Reasoning</h4>
      <p className="reasoning">{decision.reasoning}</p>

      <div className="approval-box">
        {decision.approved ? (
          <div className="approved-badge">
            ✓ Finalized — approved at {new Date(decision.approved_at!).toLocaleString()}
          </div>
        ) : (
          <>
            <input
              type="text"
              placeholder="Your name"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              disabled={approving}
            />
            <button onClick={handleApprove} disabled={approving}>
              {approving ? "Approving..." : "Approve deal"}
            </button>
            {error && <div className="error">{error}</div>}
            <p className="approval-note">
              Nothing is binding until this step (FR-8). No other action in
              this system finalizes a deal.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
