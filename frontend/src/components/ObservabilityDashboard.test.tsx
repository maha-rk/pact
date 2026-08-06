import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ObservabilityDashboard } from "./ObservabilityDashboard";
import * as api from "../api";
import type { ObservabilitySummary } from "../types";

describe("ObservabilityDashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading state before data arrives", () => {
    vi.spyOn(api, "getObservabilitySummary").mockReturnValue(new Promise(() => {}));
    render(<ObservabilityDashboard />);

    expect(screen.getByText(/Loading real statistics/)).toBeInTheDocument();
  });

  it("renders an honest unavailable message with no invented numbers when BigQuery is unreachable", async () => {
    const summary: ObservabilitySummary = {
      available: false,
      error: "403 Forbidden: caller does not have bigquery.jobUser",
      model_traces: [],
      negotiations: null,
    };
    vi.spyOn(api, "getObservabilitySummary").mockResolvedValue(summary);
    render(<ObservabilityDashboard />);

    expect(await screen.findByText(/nothing real to/)).toBeInTheDocument();
    expect(screen.getByText(/403 Forbidden/)).toBeInTheDocument();
  });

  it("renders the same unavailable message when the fetch itself rejects", async () => {
    vi.spyOn(api, "getObservabilitySummary").mockRejectedValue(new Error("Failed to fetch"));
    render(<ObservabilityDashboard />);

    expect(await screen.findByText(/nothing real to/)).toBeInTheDocument();
    expect(screen.getByText(/Failed to fetch/)).toBeInTheDocument();
  });

  it("renders real model trace bars and negotiation aggregate stats when available", async () => {
    const summary: ObservabilitySummary = {
      available: true,
      error: null,
      model_traces: [
        { model: "gemma3:4b", call_count: 40, avg_latency_ms: 812, total_tokens: 12000, error_rate: 0 },
        { model: "gemini-flash-latest", call_count: 10, avg_latency_ms: 500, total_tokens: 3000, error_rate: 0.1 },
      ],
      negotiations: {
        total_runs: 11,
        agreement_rate: 0.636,
        avg_rounds_to_agreement: 2.1,
        avg_savings_pct: 0.18,
        claim_mismatch_catch_rate: 0.9,
        compliance_rejection_rate: 0.2,
      },
    };
    vi.spyOn(api, "getObservabilitySummary").mockResolvedValue(summary);
    render(<ObservabilityDashboard />);

    expect(await screen.findByText("Gemma (self-hosted)")).toBeInTheDocument();
    expect(screen.getByText("40 calls")).toBeInTheDocument();
    expect(screen.getByText("812 ms", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("11")).toBeInTheDocument();
    expect(screen.getByText("Total runs")).toBeInTheDocument();
    expect(screen.getByText("63.6%")).toBeInTheDocument();
  });

  it("flags a nonzero error rate on a model trace row with the error styling class", async () => {
    const summary: ObservabilitySummary = {
      available: true,
      error: null,
      model_traces: [
        { model: "gemini-flash-latest", call_count: 5, avg_latency_ms: 500, total_tokens: 1000, error_rate: 1.0 },
      ],
      negotiations: null,
    };
    vi.spyOn(api, "getObservabilitySummary").mockResolvedValue(summary);
    render(<ObservabilityDashboard />);

    const errorEl = await screen.findByText(/error rate: 100.0%/);
    expect(errorEl).toHaveClass("trace-error");
  });

  it("shows an empty-state prompt when no negotiations have been logged yet", async () => {
    const summary: ObservabilitySummary = {
      available: true,
      error: null,
      model_traces: [],
      negotiations: { total_runs: 0, agreement_rate: null, avg_rounds_to_agreement: null, avg_savings_pct: null, claim_mismatch_catch_rate: null, compliance_rejection_rate: null },
    };
    vi.spyOn(api, "getObservabilitySummary").mockResolvedValue(summary);
    render(<ObservabilityDashboard />);

    expect(await screen.findByText(/No negotiations logged yet/)).toBeInTheDocument();
    expect(screen.getByText(/No model calls logged yet/)).toBeInTheDocument();
  });
});
