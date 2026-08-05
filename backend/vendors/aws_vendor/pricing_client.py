"""Real AWS pricing client, reading from a local cache of the AWS Price
List Bulk API (see refresh_pricing_cache.py -- the 480MB region index is
impractical to fetch per-request, so it's fetched and filtered once).

Key finding from the real data (checked live against AWS, not assumed):
AWS's Reserved Instance terms come only in 1-year and 3-year lengths --
there is no 3-month committed-use tier. So for any requirement with a
contract length under 12 months, the real, legitimate committed-use
discount rate is 0%: no such discount exists to legitimately claim. This
makes a claimed committed-use discount for a sub-12-month term verifiably
false by construction, not merely different from an approximated number.
"""

from __future__ import annotations

import json
from pathlib import Path

from pact.models.schemas import Requirement, VendorId

CACHE_PATH = Path(__file__).parent / "pricing_cache.json"
MIN_RESERVED_MONTHS = 12  # AWS's real minimum Reserved Instance lease length


class AWSPricingClient:
    """Implements the pact.mcp_tools.pricing_tool.PricingSource protocol."""

    def __init__(self, cache_path: Path = CACHE_PATH):
        self._cache = json.loads(cache_path.read_text())

    def list_price(self, vendor_id: VendorId, requirement: Requirement) -> float:
        hourly = self._cache["on_demand_hourly_usd"]
        hours = requirement.contract_months * 30 * 24
        return round(hourly * hours, 2)

    def real_committed_use_discount_rate(self, vendor_id: VendorId, requirement: Requirement) -> float:
        if requirement.contract_months < MIN_RESERVED_MONTHS:
            return 0.0
        on_demand = self._cache["on_demand_hourly_usd"]
        for term in self._cache["reserved_terms"]:
            if term["lease_length"] == "1yr" and term["purchase_option"] == "No Upfront":
                return round(1 - (term["hourly_usd"] / on_demand), 4)
        return 0.0

    def source_label(self, vendor_id: VendorId) -> str:
        return f"{self._cache['source']} ({self._cache['source_url']})"
