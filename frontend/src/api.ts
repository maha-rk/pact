import type { NegotiationState, VendorId } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface CreateNegotiationInput {
  gpu_count: number;
  contract_months: number;
  budget_ceiling_usd: number;
  raw_input: string;
  initial_claimed_discounts: Partial<Record<VendorId, number>>;
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
