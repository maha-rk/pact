"""Real Azure pricing client, querying the live Azure Retail Prices API
directly (no auth, no account -- confirmed keyless).

Key finding from the real data (checked live, not assumed): Azure's
Reservation terms, like AWS's, come only in 1/3/5-year lengths -- no
3-month committed-use tier exists here either. Unlike AWS, though, Azure
publishes real, genuinely-available Spot pricing with no minimum
commitment at all -- this is the honest discount lever a 3-month buyer
can legitimately claim, verified against the same live API.
"""

from __future__ import annotations

import httpx

from pact.models.schemas import Requirement, VendorId

RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"
SKU_NAME = "Standard_ND96isr_H100_v5"  # Azure's real 8x H100 VM SKU
METER_NAME = "ND96isrH100v5"  # the exact base meter name -- NOT "... Low Priority" or "... Spot"
REGION = "eastus"
MIN_RESERVED_MONTHS = 12  # Azure's real minimum Reservation term, same finding as AWS


class AzurePricingClient:
    """Implements the pact.mcp_tools.pricing_tool.PricingSource protocol."""

    def __init__(self):
        self._on_demand_hourly: float | None = None
        self._spot_hourly: float | None = None

    def _ensure_loaded(self) -> None:
        if self._on_demand_hourly is not None:
            return
        params = {
            "$filter": f"armRegionName eq '{REGION}' and armSkuName eq '{SKU_NAME}'",
        }
        resp = httpx.get(RETAIL_PRICES_URL, params=params, timeout=30.0)
        resp.raise_for_status()
        items = resp.json()["Items"]

        # Exact meter-name matches only -- "Low Priority" and "DevTest"
        # tiers share the same armSkuName and must NOT be picked up here,
        # or the discount would be computed against the wrong baseline.
        on_demand_prices = [
            i["retailPrice"]
            for i in items
            if i["type"] == "Consumption" and i["meterName"] == METER_NAME
        ]
        spot_prices = [
            i["retailPrice"]
            for i in items
            if i["type"] == "Consumption" and i["meterName"] == f"{METER_NAME} Spot"
        ]
        if not on_demand_prices:
            raise RuntimeError(f"No on-demand price found for {SKU_NAME} in {REGION}")

        self._on_demand_hourly = min(on_demand_prices)
        self._spot_hourly = min(spot_prices) if spot_prices else None

    def list_price(self, vendor_id: VendorId, requirement: Requirement) -> float:
        self._ensure_loaded()
        hours = requirement.contract_months * 30 * 24
        return round(self._on_demand_hourly * hours, 2)

    def real_committed_use_discount_rate(self, vendor_id: VendorId, requirement: Requirement) -> float:
        """For terms under Azure's real 1-year Reservation minimum, there
        is no committed-use tier -- but real Spot pricing IS legitimately
        available short-term, so that's the real discount a 3-month buyer
        can actually claim, verified against the same live source."""
        self._ensure_loaded()
        if requirement.contract_months >= MIN_RESERVED_MONTHS:
            # Real 1-year+ Reservation pricing would be looked up here;
            # out of scope for the current build (PRD non-goal: launch
            # scope is the flagship's 3-month scenario).
            return 0.0
        if self._spot_hourly is None:
            return 0.0
        return round(1 - (self._spot_hourly / self._on_demand_hourly), 4)

    def source_label(self, vendor_id: VendorId) -> str:
        return f"Azure Retail Prices API ({RETAIL_PRICES_URL})"
