import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LandingPage } from "./LandingPage";
import * as api from "../api";

describe("LandingPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getObservabilitySummary").mockResolvedValue({
      available: false,
      error: null,
      model_traces: [],
      negotiations: null,
    });
  });

  it("renders the hero, all three cards, and the proof strip", async () => {
    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={vi.fn()} />);

    expect(screen.getByText("Which vendor's claimed discount is real?")).toBeInTheDocument();
    expect(screen.getByText("What Pact does")).toBeInTheDocument();
    expect(screen.getByText("How it works")).toBeInTheDocument();
    expect(screen.getByText("Try the flagship scenario")).toBeInTheDocument();
    expect(screen.getByText("74")).toBeInTheDocument();
    expect(await screen.findByText("backend tests, real APIs")).toBeInTheDocument();
  });

  it("calls onEnterNegotiate from both the hero and the CTA card", async () => {
    const user = userEvent.setup();
    const onEnterNegotiate = vi.fn();
    render(<LandingPage onEnterNegotiate={onEnterNegotiate} onEnterObservability={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Start a negotiation →" }));
    await user.click(screen.getByRole("button", { name: "Open the negotiation console →" }));

    expect(onEnterNegotiate).toHaveBeenCalledTimes(2);
  });

  it("calls onEnterObservability from the secondary hero CTA", async () => {
    const user = userEvent.setup();
    const onEnterObservability = vi.fn();
    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={onEnterObservability} />);

    await user.click(screen.getByRole("button", { name: "See live results" }));

    expect(onEnterObservability).toHaveBeenCalledTimes(1);
  });

  it("renders live evaluation stats in the proof strip when observability data is available", async () => {
    vi.spyOn(api, "getObservabilitySummary").mockResolvedValue({
      available: true,
      error: null,
      model_traces: [],
      negotiations: {
        total_runs: 11,
        agreement_rate: 0.636,
        avg_rounds_to_agreement: 2.1,
        avg_savings_pct: 0.18,
        claim_mismatch_catch_rate: 0.9,
        compliance_rejection_rate: 0.2,
      },
    });

    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={vi.fn()} />);

    expect(await screen.findByText("11")).toBeInTheDocument();
    expect(screen.getByText("64%")).toBeInTheDocument();
  });

  it("falls back to a dash in the proof strip when observability is unavailable", async () => {
    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={vi.fn()} />);

    expect(await screen.findByText("logged evaluation runs")).toBeInTheDocument();
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });
});
