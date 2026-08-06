import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DecisionView } from "./DecisionView";
import { buildNegotiationState } from "../test/fixtures";
import * as api from "../api";

describe("DecisionView", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the selected vendor, final price, evidence, and reasoning", () => {
    const state = buildNegotiationState();
    render(<DecisionView state={state} onUpdated={vi.fn()} />);

    expect(screen.getByText("AZURE")).toBeInTheDocument();
    expect(screen.getAllByText("$39,246.00")).toHaveLength(2);
    expect(screen.getByText(/azure pricing API/)).toBeInTheDocument();
    expect(screen.getByText(/lowest verified, compliant price/)).toBeInTheDocument();
  });

  it("shows a no-deal message and skips the decision block when status is no_compliant_deal", () => {
    const state = buildNegotiationState({ status: "no_compliant_deal", decision: null });
    render(<DecisionView state={state} onUpdated={vi.fn()} />);

    expect(screen.getByText("No compliant deal found")).toBeInTheDocument();
    expect(screen.queryByText("Approve deal")).not.toBeInTheDocument();
  });

  it("shows an in-progress message when there is no decision yet", () => {
    const state = buildNegotiationState({ decision: null });
    render(<DecisionView state={state} onUpdated={vi.fn()} />);

    expect(screen.getByText(/still in progress/)).toBeInTheDocument();
  });

  it("requires an approver name before approving", async () => {
    const user = userEvent.setup();
    const approveSpy = vi.spyOn(api, "approveNegotiation");
    const state = buildNegotiationState();
    render(<DecisionView state={state} onUpdated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Approve deal" }));

    expect(screen.getByText("Enter an approver name first.")).toBeInTheDocument();
    expect(approveSpy).not.toHaveBeenCalled();
  });

  it("approves the deal and reports the finalized state upward", async () => {
    const user = userEvent.setup();
    const state = buildNegotiationState();
    const approvedState = buildNegotiationState({
      decision: { ...state.decision!, approved: true, approved_at: "2026-08-06T10:05:00Z" },
    });
    vi.spyOn(api, "approveNegotiation").mockResolvedValue(approvedState);
    const onUpdated = vi.fn();

    render(<DecisionView state={state} onUpdated={onUpdated} />);
    await user.type(screen.getByPlaceholderText("Your name"), "Mahashri");
    await user.click(screen.getByRole("button", { name: "Approve deal" }));

    await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(approvedState));
    expect(api.approveNegotiation).toHaveBeenCalledWith("neg-test-1", "Mahashri");
  });

  it("surfaces an error message when approval fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "approveNegotiation").mockRejectedValue(new Error("500 Internal Server Error"));
    const state = buildNegotiationState();

    render(<DecisionView state={state} onUpdated={vi.fn()} />);
    await user.type(screen.getByPlaceholderText("Your name"), "Mahashri");
    await user.click(screen.getByRole("button", { name: "Approve deal" }));

    expect(await screen.findByText(/500 Internal Server Error/)).toBeInTheDocument();
  });

  it("shows the approved confirmation once decision.approved is true", () => {
    const state = buildNegotiationState({
      decision: {
        ...buildNegotiationState().decision!,
        approved: true,
        approved_at: "2026-08-06T10:05:00Z",
      },
    });
    render(<DecisionView state={state} onUpdated={vi.fn()} />);

    expect(screen.getByText(/Finalized — approved at/)).toBeInTheDocument();
  });

  it("renders a truncated evidence hash and copies the full hash on click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const state = buildNegotiationState();

    render(<DecisionView state={state} onUpdated={vi.fn()} />);

    const hashEl = screen.getByTitle(state.evidence_hash!);
    expect(hashEl.textContent).toContain("…");
    expect(hashEl.textContent).not.toEqual(state.evidence_hash);

    await user.click(screen.getByRole("button", { name: "Copy hash" }));
    expect(writeText).toHaveBeenCalledWith(state.evidence_hash);
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("omits the evidence hash block entirely when evidence_hash is null", () => {
    const state = buildNegotiationState({ evidence_hash: null });
    render(<DecisionView state={state} onUpdated={vi.fn()} />);

    expect(screen.queryByText("Verifiable Evidence")).not.toBeInTheDocument();
  });
});
