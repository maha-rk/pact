#!/usr/bin/env python3
"""CLI runner for a single negotiation scenario. Currently supports the
`--fixture flagship` case for internal validation (Day 1 exit criteria);
real vendor data will be wired in as the AWS/Azure/GCP services come
online.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pact.models.schemas import AgentCard, VendorId
from pact.orchestration import approval
from pact.orchestration.graph import run_negotiation
from pact.orchestration.state import NegotiationStatus
from tests.fixtures import (
    FLAGSHIP_CLAIMED_DISCOUNTS,
    FixturePricingSource,
    flagship_policy,
    flagship_requirement,
)

CANDIDATE_VENDORS = [VendorId.AWS, VendorId.AZURE, VendorId.GCP]

AGENT_CARDS = {
    VendorId.AWS: AgentCard(vendor_id=VendorId.AWS, name="AWS Vendor Agent", endpoint="http://localhost:9001", capabilities=["negotiate"]),
    VendorId.AZURE: AgentCard(vendor_id=VendorId.AZURE, name="Azure Vendor Agent", endpoint="http://localhost:9002", capabilities=["negotiate"]),
    VendorId.GCP: AgentCard(vendor_id=VendorId.GCP, name="GCP Vendor Agent", endpoint="http://localhost:9003", capabilities=["negotiate"]),
}


def print_timeline(state) -> None:
    print(f"\n{'=' * 70}\nNEGOTIATION TIMELINE  ({state.negotiation_id})\n{'=' * 70}")
    for event in state.events:
        vendor = f"[{event.vendor_id.value.upper()}]" if event.vendor_id else "[SYSTEM]"
        round_label = f"round {event.round_number}" if event.round_number else "-"
        print(f"  {event.timestamp:%H:%M:%S}  {vendor:<9} {round_label:<10} {event.event_type.value}: {event.detail}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", choices=["flagship"], required=True)
    parser.add_argument("--approve", action="store_true", help="Also run the human approval step")
    args = parser.parse_args()

    state = run_negotiation(
        requirement=flagship_requirement(),
        policy=flagship_policy(),
        candidate_vendors=CANDIDATE_VENDORS,
        agent_cards=AGENT_CARDS,
        pricing_source=FixturePricingSource(),
        initial_claimed_discounts=dict(FLAGSHIP_CLAIMED_DISCOUNTS),
    )

    print_timeline(state)

    print(f"\n{'=' * 70}\nDECISION / EVIDENCE / REASONING\n{'=' * 70}")
    d = state.decision
    print(f"  Status:          {state.status.value}")
    print(f"  Selected vendor:  {d.selected_vendor.value if d.selected_vendor else 'none'}")
    print(f"  Final price:      ${d.final_price_usd:,.2f}" if d.final_price_usd else "  Final price:      n/a")
    print("  Evidence:")
    for item in d.evidence:
        print(f"    - {item.label}: {item.value}  (source: {item.source})")
    print(f"  Reasoning:        {d.reasoning}")

    if args.approve and state.status == NegotiationStatus.AGREED_PENDING_APPROVAL:
        approval.approve(state, approved_by="cli-demo-user")
        print(f"\n  >>> Approved by cli-demo-user. Status: {state.status.value}")


if __name__ == "__main__":
    main()
