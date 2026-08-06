import type { NegotiationState, ObservabilitySummary, VendorId } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface CreateNegotiationInput {
  gpu_count: number;
  contract_months: number;
  budget_ceiling_usd: number;
  raw_input: string;
  initial_claimed_discounts: Partial<Record<VendorId, number>>;
}

export interface ParsedRequirement {
  gpu_type: string | null;
  gpu_count: number | null;
  contract_months: number | null;
  budget_ceiling_usd: number | null;
  region: string | null;
  raw_input: string;
  guardrail_warnings: string[];
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  return resp.json();
}

export function createNegotiation(input: CreateNegotiationInput): Promise<NegotiationState> {
  return fetch(`${API_BASE}/negotiations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  }).then((r) => handle<NegotiationState>(r));
}

export function getNegotiation(id: string): Promise<NegotiationState> {
  return fetch(`${API_BASE}/negotiations/${id}`).then((r) => handle<NegotiationState>(r));
}

export function approveNegotiation(id: string, approvedBy: string): Promise<NegotiationState> {
  return fetch(`${API_BASE}/negotiations/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_by: approvedBy }),
  }).then((r) => handle<NegotiationState>(r));
}

export function parseRequirementFromImage(file: File): Promise<ParsedRequirement> {
  const body = new FormData();
  body.append("image", file);
  return fetch(`${API_BASE}/requirements/parse-image`, { method: "POST", body }).then((r) =>
    handle<ParsedRequirement>(r)
  );
}

export function parseRequirementFromText(text: string): Promise<ParsedRequirement> {
  const body = new FormData();
  body.append("text", text);
  return fetch(`${API_BASE}/requirements/parse-text`, { method: "POST", body }).then((r) =>
    handle<ParsedRequirement>(r)
  );
}

export function getObservabilitySummary(): Promise<ObservabilitySummary> {
  return fetch(`${API_BASE}/observability/summary`).then((r) => handle<ObservabilitySummary>(r));
}

export function evidenceExportUrl(negotiationId: string): string {
  return `${API_BASE}/negotiations/${negotiationId}/evidence`;
}
