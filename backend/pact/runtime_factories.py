"""Factories for the real-or-gracefully-degraded dependencies the API
wires into a negotiation run. Each one probes for real availability and
returns `None` (or an in-process fallback) rather than raising -- a
missing optional dependency must never block a negotiation (PRD §27).

Extracted from `pact/api/routes_negotiation.py` so the same factories can
be reused by the distributed worker (`pact/worker/negotiation_worker.py`),
which needs to resolve its own pricing/narration/screening dependencies
in a separate process rather than receiving them by object reference."""

from __future__ import annotations

import os

from pact.models.schemas import VendorId


def pricing_source():
    """`PACT_FIXTURE_MODE=true` selects the fixture pricing source used by
    fast offline tests and the distributed determinism test (never shown
    to a user or judge as a real result -- see
    `pact/testing_support/fixture_pricing.py`). Otherwise, the real,
    live AWS/Azure pricing clients."""
    if os.environ.get("PACT_FIXTURE_MODE") == "true":
        from pact.testing_support.fixture_pricing import FixturePricingSource

        return FixturePricingSource()

    # Imported lazily so importing this module doesn't require the vendor
    # packages to be on the path in every deployment context.
    from vendors.aws_vendor.pricing_client import AWSPricingClient
    from vendors.azure_vendor.pricing_client import AzurePricingClient

    aws, azure = AWSPricingClient(), AzurePricingClient()

    class _Combined:
        def list_price(self, vendor_id, requirement):
            return (aws if vendor_id == VendorId.AWS else azure).list_price(vendor_id, requirement)

        def real_committed_use_discount_rate(self, vendor_id, requirement):
            client = aws if vendor_id == VendorId.AWS else azure
            return client.real_committed_use_discount_rate(vendor_id, requirement)

        def source_label(self, vendor_id):
            return (aws if vendor_id == VendorId.AWS else azure).source_label(vendor_id)

    return _Combined()


def vendor_client(endpoints: dict[VendorId, str]):
    """`PACT_FIXTURE_MODE=true` returns `None`, which `run_negotiation`
    already treats as "compute vendor offers in-process with the same
    deterministic math the vendor services call internally" -- the exact
    mechanism the existing flagship e2e tests rely on."""
    if os.environ.get("PACT_FIXTURE_MODE") == "true":
        return None
    from pact.a2a.vendor_client import HttpVendorClient

    return HttpVendorClient(endpoints)


def narrator():
    """Real Gemini narration if a key is configured; `None` otherwise --
    the deterministic template fallback in decision_agent handles that
    case gracefully (PRD §27)."""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from pact.models.gemini_client import narrate_reasoning

    return narrate_reasoning


def plausibility_screener():
    """Real Gemma pre-screen if the local Ollama instance is reachable;
    `None` otherwise -- verification's deterministic verdict never depends
    on this (PRD §27)."""
    import httpx

    try:
        httpx.get("http://localhost:11434/api/tags", timeout=1.0).raise_for_status()
    except Exception:
        return None
    from pact.models.gemma_client import plausibility_screen

    return plausibility_screen
