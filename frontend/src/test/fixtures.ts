import type { NegotiationState } from "../types";

export function buildNegotiationState(overrides: Partial<NegotiationState> = {}): NegotiationState {
  return {
    negotiation_id: "neg-test-1",
    requirement: {
      gpu_type: "H100",
      gpu_count: 8,
      contract_months: 3,
      budget_ceiling_usd: 115000,
      region: null,
      raw_input: "Need 8 H100 GPUs, 3-month contract, $115,000 budget",
    },
    policy: {
      budget_ceiling_usd: 115000,
      blocked_vendors: [],
      required_certifications: [],
    },
    status: "finalized",
    active_vendors: ["aws", "azure"],
    unavailable_vendors: [],
    offers: [
      { vendor_id: "aws", round_number: 1, price_usd: 42000, claimed_discount_rate: 0.25, timestamp: "2026-08-06T10:00:00Z" },
      { vendor_id: "azure", round_number: 1, price_usd: 39246, claimed_discount_rate: 0.8152, timestamp: "2026-08-06T10:00:01Z" },
    ],
    verification_results: [
      {
        vendor_id: "azure",
        claim_checked: "discount_rate",
        claimed_value: 0.8152,
        actual_value: 0.4,
        source: "azure pricing API",
        matched: false,
        checked_at: "2026-08-06T10:00:02Z",
      },
    ],
    compliance_results: [
      {
        vendor_id: "azure",
        constraint_name: "budget_ceiling_usd",
        passed: true,
        detail: "39246 <= 115000",
        checked_at: "2026-08-06T10:00:03Z",
      },
    ],
    events: [
      { event_type: "requirement_received", vendor_id: null, round_number: null, detail: "8x H100, 3mo, $115,000", timestamp: "2026-08-06T10:00:00Z", chain_hash: "1".repeat(64) },
      { event_type: "offer_made", vendor_id: "azure", round_number: 1, detail: "$39,246", timestamp: "2026-08-06T10:00:01Z", chain_hash: "2".repeat(64) },
      { event_type: "claim_rejected", vendor_id: "azure", round_number: 1, detail: "claimed 81.52% discount, actual 40%", timestamp: "2026-08-06T10:00:02Z", chain_hash: "3".repeat(64) },
      { event_type: "compliance_rejected", vendor_id: "aws", round_number: 1, detail: "blocked vendor", timestamp: "2026-08-06T10:00:03Z", chain_hash: "4".repeat(64) },
      { event_type: "decision_produced", vendor_id: "azure", round_number: null, detail: "Azure selected", timestamp: "2026-08-06T10:00:04Z", chain_hash: "5".repeat(64) },
    ],
    decision: {
      negotiation_id: "neg-test-1",
      selected_vendor: "azure",
      final_price_usd: 39246,
      evidence: [
        { label: "Final price", value: "$39,246.00", source: "azure pricing API" },
      ],
      reasoning: "Azure offered the lowest verified, compliant price.",
      approved: false,
      approved_at: null,
    },
    evidence_hash: "a".repeat(64),
    ...overrides,
  };
}
