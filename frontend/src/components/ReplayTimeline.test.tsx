import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReplayTimeline } from "./ReplayTimeline";
import { buildNegotiationState } from "../test/fixtures";

describe("ReplayTimeline", () => {
  it("renders one row per event, in order, with human-readable labels", () => {
    const state = buildNegotiationState();
    render(<ReplayTimeline state={state} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(state.events.length);
    expect(items[0]).toHaveTextContent("Requirement received");
    expect(items[2]).toHaveTextContent("Claim rejected");
    expect(items[3]).toHaveTextContent("Compliance rejected");
  });

  it("marks rejection events with the negative styling class", () => {
    const state = buildNegotiationState();
    render(<ReplayTimeline state={state} />);

    const rejected = screen.getByText("claimed 81.52% discount, actual 40%").closest("li");
    expect(rejected).toHaveClass("event-negative");
  });

  it("falls back to the raw event_type string for unknown event types", () => {
    const state = buildNegotiationState({
      events: [
        // @ts-expect-error deliberately exercising the unknown-type fallback path
        { event_type: "something_new", vendor_id: null, round_number: null, detail: "n/a", timestamp: "2026-08-06T10:00:00Z" },
      ],
    });
    render(<ReplayTimeline state={state} />);

    expect(screen.getByText("something_new")).toBeInTheDocument();
  });

  it("shows the audit chain head and a per-event chain hash badge", () => {
    const state = buildNegotiationState();
    render(<ReplayTimeline state={state} />);

    const lastEvent = state.events[state.events.length - 1];
    expect(screen.getByTitle(lastEvent.chain_hash!)).toBeInTheDocument();
    expect(screen.getByText(/hash-chained to the one before it/)).toBeInTheDocument();

    const firstEvent = state.events[0];
    expect(screen.getByTitle(`Audit chain hash: ${firstEvent.chain_hash}`)).toBeInTheDocument();
  });

  it("renders vendor and round badges only when present on the event", () => {
    const state = buildNegotiationState({
      events: [
        { event_type: "offer_made", vendor_id: "aws", round_number: 2, detail: "$40,000", timestamp: "2026-08-06T10:00:00Z", chain_hash: "a".repeat(64) },
        { event_type: "requirement_received", vendor_id: null, round_number: null, detail: "intake", timestamp: "2026-08-06T10:00:00Z", chain_hash: "b".repeat(64) },
      ],
    });
    render(<ReplayTimeline state={state} />);

    expect(screen.getByText("AWS")).toBeInTheDocument();
    expect(screen.getByText("R2")).toBeInTheDocument();
  });
});
