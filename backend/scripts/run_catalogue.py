#!/usr/bin/env python3
"""Evaluation harness runner (PRD §29, ARCHITECTURE.md §5). Runs every
scenario in eval/scenario_catalogue.yaml through the exact same pipeline
code path as the flagship run -- no separate "eval mode" -- and computes
real aggregate statistics from the actual results.

Writes eval/results.json locally (for the printed summary table) AND
sinks every scenario run to BigQuery via the same bigquery_sink used by
the live API -- the exact same tables, the exact same code path, so
infra/bigquery/queries_aggregate.sql computes real aggregate statistics
from real logged runs, not a separate mechanism (PRD §25).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pact.logging import bigquery_sink
from pact.models.schemas import AgentCard, PolicyConstraints, Requirement, VendorId
from pact.orchestration.graph import run_negotiation
from pact.orchestration.state import NegotiationStatus

CATALOGUE_PATH = Path(__file__).resolve().parent.parent / "eval" / "scenario_catalogue.yaml"
RESULTS_PATH = Path(__file__).resolve().parent.parent / "eval" / "results.json"

KNOWN_CERTIFICATIONS = {
    VendorId.AWS: ["SOC2", "ISO27001"],
    VendorId.AZURE: ["SOC2", "ISO27001"],
    VendorId.GCP: ["SOC2", "ISO27001"],
}


class _ScenarioPricingSource:
    """Per-scenario fixture pricing, explicitly labeled as such -- never
    presented as a real live quote (see tests/fixtures.py for the same
    discipline applied to the flagship scenario)."""

    def __init__(self, vendor_configs: dict):
        self._configs = vendor_configs

    def list_price(self, vendor_id, requirement):
        return self._configs[vendor_id]["list_price"]

    def real_committed_use_discount_rate(self, vendor_id, requirement):
        return self._configs[vendor_id]["real_discount"]

    def source_label(self, vendor_id):
        return f"scenario catalogue fixture ({vendor_id.value})"


def run_scenario(scenario: dict, sink_to_bigquery: bool = False) -> dict:
    """`sink_to_bigquery` defaults to False so tests importing this
    function stay fast and don't write real rows on every run; the CLI
    entrypoint below (`main()`) passes True -- that's the one real
    invocation meant to populate BigQuery."""
    vendor_configs = {
        VendorId(vid): cfg for vid, cfg in scenario["vendors"].items()
    }
    candidate_vendors = list(vendor_configs.keys())

    requirement = Requirement(
        gpu_type="H100",
        gpu_count=scenario["requirement"]["gpu_count"],
        contract_months=scenario["requirement"]["contract_months"],
        budget_ceiling_usd=scenario["requirement"]["budget_ceiling_usd"],
        raw_input=scenario["description"],
    )
    policy = PolicyConstraints(
        budget_ceiling_usd=scenario["requirement"]["budget_ceiling_usd"],
        blocked_vendors=[VendorId(v) for v in scenario.get("blocked_vendors", [])],
        required_certifications=scenario.get("required_certifications", []),
    )
    agent_cards = {
        vid: AgentCard(
            vendor_id=vid,
            name=f"{vid.value.upper()} Vendor Agent",
            endpoint=f"http://fixture/{vid.value}",
            capabilities=["negotiate"],
            certifications=KNOWN_CERTIFICATIONS.get(vid, []),
        )
        for vid in candidate_vendors
    }
    initial_claimed_discounts = {vid: cfg["claimed_discount"] for vid, cfg in vendor_configs.items()}

    state = run_negotiation(
        requirement=requirement,
        policy=policy,
        candidate_vendors=candidate_vendors,
        agent_cards=agent_cards,
        pricing_source=_ScenarioPricingSource(vendor_configs),
        initial_claimed_discounts=initial_claimed_discounts,
    )
    if sink_to_bigquery:
        bigquery_sink.write_negotiation(state)  # same sink, same tables as the live API (PRD §25)

    compliant = state.status == NegotiationStatus.AGREED_PENDING_APPROVAL
    claim_caught = any(not r.matched for r in state.verification_results)
    compliance_caught = any(not c.passed for c in state.compliance_results)
    savings_pct = None
    rounds_to_agreement = None
    if compliant and state.decision and state.decision.final_price_usd is not None:
        winning_vendor = state.decision.selected_vendor
        opening_price = vendor_configs[winning_vendor]["list_price"]
        savings_pct = (opening_price - state.decision.final_price_usd) / opening_price
        winning_offers = [o for o in state.offers if o.vendor_id == winning_vendor]
        rounds_to_agreement = max(o.round_number for o in winning_offers) if winning_offers else None

    expected_outcome = scenario["dimensions"].get("outcome")
    actual_outcome = "compliant" if compliant else "no_deal"

    return {
        "id": scenario["id"],
        "description": scenario["description"],
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "outcome_matches_expectation": expected_outcome == actual_outcome,
        "compliant": compliant,
        "selected_vendor": state.decision.selected_vendor.value if compliant and state.decision.selected_vendor else None,
        "final_price_usd": state.decision.final_price_usd if compliant else None,
        "savings_pct": savings_pct,
        "rounds_to_agreement": rounds_to_agreement,
        "claim_mismatch_caught": claim_caught,
        "compliance_rejection_occurred": compliance_caught,
        "event_count": len(state.events),
    }


def main() -> None:
    catalogue = yaml.safe_load(CATALOGUE_PATH.read_text())
    results = [run_scenario(s, sink_to_bigquery=True) for s in catalogue["scenarios"]]

    RESULTS_PATH.write_text(json.dumps(results, indent=2))

    print(f"\n{'ID':<32} {'Expected':<10} {'Actual':<10} {'Match':<6} {'Vendor':<8} {'Price':<14} {'Rounds':<7} {'Savings':<8}")
    print("-" * 100)
    for r in results:
        price = f"${r['final_price_usd']:,.0f}" if r["final_price_usd"] else "-"
        savings = f"{r['savings_pct']:.1%}" if r["savings_pct"] is not None else "-"
        match = "OK" if r["outcome_matches_expectation"] else "MISMATCH"
        print(
            f"{r['id']:<32} {r['expected_outcome']:<10} {r['actual_outcome']:<10} {match:<6} "
            f"{r['selected_vendor'] or '-':<8} {price:<14} {str(r['rounds_to_agreement'] or '-'):<7} {savings:<8}"
        )

    n = len(results)
    compliant_results = [r for r in results if r["compliant"]]
    agreement_rate = len(compliant_results) / n
    avg_rounds = mean(r["rounds_to_agreement"] for r in compliant_results) if compliant_results else None
    avg_savings = mean(r["savings_pct"] for r in compliant_results) if compliant_results else None
    claim_catch_rate = sum(r["claim_mismatch_caught"] for r in results) / n
    compliance_catch_rate = sum(r["compliance_rejection_occurred"] for r in results) / n
    all_match_expectation = all(r["outcome_matches_expectation"] for r in results)

    print("\n" + "=" * 60)
    print("AGGREGATE STATISTICS (computed from the runs above, real, not invented)")
    print("=" * 60)
    print(f"  Scenarios run:              {n}")
    print(f"  Agreement rate:             {agreement_rate:.1%}")
    print(f"  Avg rounds-to-agreement:    {avg_rounds:.1f}" if avg_rounds is not None else "  Avg rounds-to-agreement:    n/a")
    print(f"  Avg savings vs list price:  {avg_savings:.1%}" if avg_savings is not None else "  Avg savings vs list price:  n/a")
    print(f"  Claim-mismatch catch rate:  {claim_catch_rate:.1%}")
    print(f"  Compliance-rejection rate:  {compliance_catch_rate:.1%}")
    print(f"  All outcomes matched catalogue expectations: {all_match_expectation}")
    print(f"\nFull results written to {RESULTS_PATH}")

    if not all_match_expectation:
        print("\n⚠ WARNING: at least one scenario's actual outcome did not match its catalogue expectation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
