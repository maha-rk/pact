import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
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

  it("renders the hero, the how-it-works steps, and the proof strip", async () => {
    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={vi.fn()} />);

    expect(screen.getByText("Autonomous procurement for the agent economy.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "The 6-Step Process: From Requirement to Decision, in Seconds" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buyer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Discovery" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Negotiation" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Verification" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: "Compliance" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: "Decision" }).length).toBeGreaterThan(0);
    expect(await screen.findByText("79", {}, { timeout: 6000 })).toBeInTheDocument();
    expect(screen.getByText("backend tests, real APIs")).toBeInTheDocument();
  });

  it("renders the Today vs. Pact, flagship walkthrough, and no-scoring sections with real content", () => {
    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={vi.fn()} />);

    expect(screen.getByText("From Spreadsheets to Agents")).toBeInTheDocument();
    expect(screen.getByText("The Flagship Scenario")).toBeInTheDocument();
    expect(screen.getByText("$39,246.20")).toBeInTheDocument();
    expect(screen.getByText("No such discount tier exists under 12 months", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Pact doesn't Score Vendors")).toBeInTheDocument();
  });

  it("renders the why-trust section, leading with why before how or proof", () => {
    const { container } = render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={vi.fn()} />);

    expect(screen.getByText("Why Agent Commerce Needs Trust")).toBeInTheDocument();
    const trustSection = container.querySelector("#trust") as HTMLElement;
    expect(within(trustSection).getByRole("heading", { name: "Verification" })).toBeInTheDocument();
    expect(within(trustSection).getByRole("heading", { name: "Compliance" })).toBeInTheDocument();
    expect(within(trustSection).getByRole("heading", { name: "Evidence" })).toBeInTheDocument();

    const sectionIds = Array.from(container.querySelectorAll("section[id]")).map((el) => el.id);
    expect(sectionIds.indexOf("trust")).toBeLessThan(sectionIds.indexOf("how-it-works"));
    expect(sectionIds.indexOf("trust")).toBeLessThan(sectionIds.indexOf("comparison"));
    expect(sectionIds.indexOf("how-it-works")).toBeLessThan(sectionIds.indexOf("example"));
  });

  it("calls onEnterNegotiate from both the hero and the how-it-works CTA", async () => {
    const user = userEvent.setup();
    const onEnterNegotiate = vi.fn();
    render(<LandingPage onEnterNegotiate={onEnterNegotiate} onEnterObservability={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Start a negotiation →" }));
    await user.click(screen.getByRole("button", { name: "Try the flagship scenario →" }));

    expect(onEnterNegotiate).toHaveBeenCalledTimes(2);
  });

  it("calls onEnterObservability from the secondary hero CTA", async () => {
    const user = userEvent.setup();
    const onEnterObservability = vi.fn();
    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={onEnterObservability} />);

    await user.click(screen.getByRole("button", { name: "See live results →" }));

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

    expect(await screen.findByText("11", {}, { timeout: 6000 })).toBeInTheDocument();
  });

  it("falls back to a dash in the proof strip when observability is unavailable", async () => {
    render(<LandingPage onEnterNegotiate={vi.fn()} onEnterObservability={vi.fn()} />);

    expect(await screen.findByText("logged evaluation runs")).toBeInTheDocument();
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });
});
