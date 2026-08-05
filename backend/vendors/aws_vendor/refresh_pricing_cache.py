#!/usr/bin/env python3
"""Refresh the local AWS pricing cache from the real AWS Price List Bulk
API. The full region index (~480MB) is impractical to fetch per-request,
so this script streams it once, extracts only the p5.48xlarge (8x H100)
SKU's real on-demand and reserved-instance pricing for us-east-1, and
writes a small cache file the vendor service reads at request time.

Run manually / on a schedule -- not on every request. Real data, cached
for speed, not replaced with anything invented.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import ijson

REGION = "us-east-1"
INSTANCE_TYPE = "p5.48xlarge"  # AWS's real 8x H100 instance type
INDEX_URL = f"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/{REGION}/index.json"
CACHE_PATH = Path(__file__).parent / "pricing_cache.json"


def refresh() -> dict:
    print(f"Fetching {INDEX_URL} ...")
    tmp_path = Path("/tmp/aws_ec2_pricing_index.json")
    urllib.request.urlretrieve(INDEX_URL, tmp_path)

    on_demand_sku = None
    products = {}
    print("Scanning products for on-demand p5.48xlarge SKU...")
    with open(tmp_path, "rb") as f:
        for key, product in ijson.kvitems(f, "products"):
            attrs = product.get("attributes", {})
            if (
                attrs.get("instanceType") == INSTANCE_TYPE
                and attrs.get("operatingSystem") == "Linux"
                and attrs.get("tenancy") == "Shared"
                and attrs.get("preInstalledSw") == "NA"
                and attrs.get("capacitystatus") == "Used"
                and attrs.get("marketoption") == "OnDemand"
            ):
                on_demand_sku = product["sku"]
                products[on_demand_sku] = attrs
                break

    if on_demand_sku is None:
        raise RuntimeError(f"Could not find on-demand SKU for {INSTANCE_TYPE} in {REGION}")

    on_demand_price = None
    reserved_terms: list[dict] = []

    print("Extracting on-demand price...")
    with open(tmp_path, "rb") as f:
        for sku, terms in ijson.kvitems(f, "terms.OnDemand"):
            if sku == on_demand_sku:
                for term in terms.values():
                    for dim in term["priceDimensions"].values():
                        on_demand_price = float(dim["pricePerUnit"]["USD"])
                break

    print("Extracting reserved-instance terms...")
    with open(tmp_path, "rb") as f:
        for sku, terms in ijson.kvitems(f, "terms.Reserved"):
            if sku == on_demand_sku:
                for term in terms.values():
                    attrs = term["termAttributes"]
                    hourly = None
                    for dim in term["priceDimensions"].values():
                        if dim["unit"] == "Hrs":
                            hourly = float(dim["pricePerUnit"]["USD"])
                    if hourly is not None:
                        reserved_terms.append(
                            {
                                "lease_length": attrs["LeaseContractLength"],
                                "purchase_option": attrs["PurchaseOption"],
                                "offering_class": attrs["OfferingClass"],
                                "hourly_usd": hourly,
                            }
                        )
                break

    cache = {
        "instance_type": INSTANCE_TYPE,
        "region": REGION,
        "gpu_count": 8,
        "gpu_type": "H100",
        "on_demand_hourly_usd": on_demand_price,
        "reserved_terms": reserved_terms,
        "source": "AWS Price List Bulk API",
        "source_url": INDEX_URL,
    }
    CACHE_PATH.write_text(json.dumps(cache, indent=2))
    print(f"Wrote cache to {CACHE_PATH}")
    print(json.dumps(cache, indent=2))
    return cache


if __name__ == "__main__":
    refresh()
