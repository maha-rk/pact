import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { buildNegotiationState } from "./test/fixtures";
import * as api from "./api";

async function enterNegotiate(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Start a negotiation →" }));
}

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getObservabilitySummary").mockResolvedValue({
      available: false,
      error: null,
      model_traces: [],
      negotiations: null,
    });
  });

  it("shows the landing page first, not the negotiation form", () => {
    render(<App />);

    expect(screen.getByText("Autonomous procurement for the agent economy.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Requirement", level: 2 })).not.toBeInTheDocument();
  });

  it("enters the negotiate view from the landing page's primary CTA", async () => {
    const user = userEvent.setup();
    render(<App />);

    await enterNegotiate(user);

    expect(screen.getByText("Requirement")).toBeInTheDocument();
    expect(screen.getByDisplayValue("8")).toBeInTheDocument();
    expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    expect(screen.getByDisplayValue("115000")).toBeInTheDocument();
    expect(screen.queryByText(/Decision \/ Evidence \/ Reasoning/)).not.toBeInTheDocument();
  });

  it("enters the observability view from the landing page's secondary CTA", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "See live results →" }));

    expect(await screen.findByText(/nothing real to/)).toBeInTheDocument();
  });

  it("returns to the landing page when the app brand is clicked", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await enterNegotiate(user);

    const brandButton = container.querySelector(".app-brand");
    expect(brandButton).not.toBeNull();
    await user.click(brandButton as HTMLElement);

    expect(screen.getByText("Autonomous procurement for the agent economy.")).toBeInTheDocument();
  });

  it("runs a negotiation and renders the resulting decision tab", async () => {
    const user = userEvent.setup();
    const state = buildNegotiationState();
    vi.spyOn(api, "createNegotiation").mockResolvedValue(state);

    render(<App />);
    await enterNegotiate(user);
    await user.click(screen.getByRole("button", { name: "Start negotiation" }));

    expect(await screen.findByText("AZURE")).toBeInTheDocument();
    expect(screen.getByText(/Negotiation Replay \(5 events\)/)).toBeInTheDocument();
  });

  it("switches between the Decision and Replay tabs", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "createNegotiation").mockResolvedValue(buildNegotiationState());

    render(<App />);
    await enterNegotiate(user);
    await user.click(screen.getByRole("button", { name: "Start negotiation" }));
    await screen.findByText("AZURE");

    await user.click(screen.getByRole("button", { name: /Negotiation Replay/ }));
    expect(screen.getByText("Requirement received")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Decision \/ Evidence \/ Reasoning/ }));
    expect(screen.getByText("AZURE")).toBeInTheDocument();
  });

  it("shows a request-failed error when the backend call rejects", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "createNegotiation").mockRejectedValue(new Error("503 Service Unavailable"));

    render(<App />);
    await enterNegotiate(user);
    await user.click(screen.getByRole("button", { name: "Start negotiation" }));

    expect(await screen.findByText(/Request failed: 503 Service Unavailable/)).toBeInTheDocument();
  });

  it("updates form fields as the user edits them", async () => {
    const user = userEvent.setup();
    render(<App />);
    await enterNegotiate(user);

    const gpuInput = screen.getByLabelText("GPU count");
    await user.clear(gpuInput);
    await user.type(gpuInput, "16");

    expect(screen.getByDisplayValue("16")).toBeInTheDocument();
  });

  it("switches to the Observability view and back", async () => {
    const user = userEvent.setup();
    render(<App />);
    await enterNegotiate(user);

    await user.click(screen.getByRole("button", { name: "Observability" }));
    expect(await screen.findByText(/nothing real to/)).toBeInTheDocument();
    expect(screen.queryByText("Requirement")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Negotiate" }));
    expect(screen.getByText("Requirement")).toBeInTheDocument();
  });

  it("passes the current form values to createNegotiation on submit", async () => {
    const user = userEvent.setup();
    const createSpy = vi.spyOn(api, "createNegotiation").mockResolvedValue(buildNegotiationState());

    render(<App />);
    await enterNegotiate(user);
    await user.click(screen.getByRole("button", { name: "Start negotiation" }));

    await waitFor(() =>
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          gpu_count: 8,
          contract_months: 3,
          budget_ceiling_usd: 115000,
        })
      )
    );
  });
});
