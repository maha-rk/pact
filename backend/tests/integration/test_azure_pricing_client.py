"""Integration test against the real, live Azure Retail Prices API
(PRD §30's 'integration tests against real external dependency')."""

from pact.models.schemas import Requirement, VendorId
from vendors.azure_vendor.pricing_client import AzurePricingClient


def _requirement(months: int) -> Requirement:
    return Requirement(
        gpu_type="H100", gpu_count=8, contract_months=months, budget_ceiling_usd=0, raw_input="test"
    )


def test_on_demand_price_is_real_and_positive():
    client = AzurePricingClient()
    price = client.list_price(VendorId.AZURE, _requirement(3))
    assert price > 0
    assert price > 1000


def test_no_committed_use_reservation_tier_under_one_year():
    client = AzurePricingClient()
    rate = client.real_committed_use_discount_rate(VendorId.AZURE, _requirement(3))
    # Azure has no reservation tier under 1 year, but DOES have real spot
    # pricing, so the real discount here is spot-based and substantial.
    assert 0.5 < rate < 1.0


def test_spot_discount_is_grounded_in_real_on_demand_and_spot_prices():
    client = AzurePricingClient()
    client._ensure_loaded()
    assert client._on_demand_hourly is not None
    assert client._spot_hourly is not None
    assert client._spot_hourly < client._on_demand_hourly


def test_source_label_cites_the_real_azure_api():
    client = AzurePricingClient()
    label = client.source_label(VendorId.AZURE)
    assert "prices.azure.com" in label
