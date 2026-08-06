"""Runs the full scenario catalogue (PRD §18) through the complete
pipeline and asserts every outcome matches the catalogue's own stated
expectation -- PRD §30's end-to-end testing requirement."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import yaml
from run_catalogue import CATALOGUE_PATH, run_scenario  # noqa: E402


def _load_scenarios():
    return yaml.safe_load(CATALOGUE_PATH.read_text())["scenarios"]


def test_every_scenario_outcome_matches_its_catalogue_expectation():
    scenarios = _load_scenarios()
    results = [run_scenario(s) for s in scenarios]
    mismatches = [r["id"] for r in results if not r["outcome_matches_expectation"]]
    assert not mismatches, f"Scenarios with unexpected outcomes: {mismatches}"


def test_catalogue_exercises_both_demo_critical_behaviors():
    scenarios = _load_scenarios()
    results = [run_scenario(s) for s in scenarios]
    assert any(r["claim_mismatch_caught"] for r in results), "No scenario caught a claim mismatch"
    assert any(r["compliance_rejection_occurred"] for r in results), "No scenario triggered a compliance rejection"


def test_catalogue_covers_both_compliant_and_no_deal_outcomes():
    scenarios = _load_scenarios()
    results = [run_scenario(s) for s in scenarios]
    assert any(r["compliant"] for r in results)
    assert any(not r["compliant"] for r in results)
