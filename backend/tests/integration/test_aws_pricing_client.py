"""Integration test against the real AWS pricing cache (populated from the
live AWS Price List Bulk API by refresh_pricing_cache.py -- PRD §30's
'integration tests against real external dependency' requirement)."""

import pytest

from pact.models.schemas import Requirement, VendorId
from vendors.aws_vendor.pricing_client import CACHE_PATH, AWSPricingClient

pytestmark = pytest.mark.skipif(
    not CACHE_PATH.exists(), reason="pricing cache not populated; run refresh_pricing_cache.py first"
)


def _requirement(months: int) -> Requirement:
    return Requirement(
        gpu_type="H100",
        gpu_count=8,
        contract_months=months,
        budget_ceiling_usd=10000.0,
        raw_input="test",
    )


def test_on_demand_price_is_real_and_positive():
    client = AWSPricingClient()
    price = client.list_price(VendorId.AWS, _requirement(3))
    assert price > 0
    # 8x H100 (p5.48xlarge) on-demand should be well into four figures for a month
    assert price > 1000


def test_no_committed_use_discount_exists_under_aws_real_minimum_term():
    """AWS's real Reserved Instance minimum lease length is 1 year -- a
    3-month commitment has no legitimate discount tier at all."""
    client = AWSPricingClient()
    rate = client.real_committed_use_discount_rate(VendorId.AWS, _requirement(3))
    assert rate == 0.0


def test_real_discount_exists_at_or_above_one_year_term():
    client = AWSPricingClient()
    rate = client.real_committed_use_discount_rate(VendorId.AWS, _requirement(12))
    assert 0.0 < rate < 1.0


def test_source_label_cites_the_real_aws_api():
    client = AWSPricingClient()
    label = client.source_label(VendorId.AWS)
    assert "AWS Price List Bulk API" in label
    assert "pricing.us-east-1.amazonaws.com" in label
