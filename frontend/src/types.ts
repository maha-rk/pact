// Mirrors backend/pact/models/schemas.py and orchestration/state.py.
// Both UI surfaces below render projections of this one shape (PRD §22).

export type VendorId = "aws" | "azure" | "gcp" | "runpod";

export interface Requirement {
  gpu_type: string;
  gpu_count: number;
  contract_months: number;
  budget_ceiling_usd: number;
  region: string | null;
  raw_input: string;
}

export interface PolicyConstraints {
  budget_ceiling_usd: number;
  blocked_vendors: VendorId[];
  required_certifications: string[];
}

export interface Offer {
  vendor_id: VendorId;
  round_number: number;
  price_usd: number;
  claimed_discount_rate: number | null;
  timestamp: string;
}

export interface VerificationResult {
  vendor_id: VendorId;
  claim_checked: string;
  claimed_value: number;
  actual_value: number;
  source: string;
  matched: boolean;
  checked_at: string;
}

export interface ComplianceResult {
  vendor_id: VendorId;
  constraint_name: string;
  passed: boolean;
  detail: string;
  checked_at: string;
}

export interface EvidenceItem {
  label: string;
  value: string;
  source: string;
}

export interface Decision {
  negotiation_id: string;
  selected_vendor: VendorId | null;
  final_price_usd: number | null;
  evidence: EvidenceItem[];
  reasoning: string;
  approved: boolean;
  approved_at: string | null;
}

export type EventType =
  | "requirement_received"
  | "vendor_discovered"
  | "offer_made"
  | "claim_verified"
  | "claim_rejected"
  | "renegotiation_triggered"
  | "compliance_passed"
  | "compliance_rejected"
  | "decision_produced"
  | "decision_approved"
  | "no_compliant_deal"
  | "vendor_unavailable";

export interface NegotiationEvent {
  event_type: EventType;
  vendor_id: VendorId | null;
  round_number: number | null;
  detail: string;
  timestamp: string;
}

export type NegotiationStatus =
  | "in_progress"
  | "agreed_pending_approval"
  | "finalized"
  | "no_compliant_deal";

export interface NegotiationState {
  negotiation_id: string;
  requirement: Requirement;
  policy: PolicyConstraints;
  status: NegotiationStatus;
  active_vendors: VendorId[];
  unavailable_vendors: VendorId[];
  offers: Offer[];
  verification_results: VerificationResult[];
  compliance_results: ComplianceResult[];
  events: NegotiationEvent[];
  decision: Decision | null;
}
