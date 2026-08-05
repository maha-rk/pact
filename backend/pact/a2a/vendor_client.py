"""HTTP-based transport for the Negotiation Agent <-> each Vendor Agent
link (PRD §17, §24). Each vendor is a genuinely separate FastAPI process
with its own Agent Card and endpoint; this client speaks plain HTTP/JSON
to them.

Honest scope note: the official `a2a-sdk` package (v1.1.2) was evaluated
for this link specifically, per the build plan's instruction to attempt
real A2A SDK integration first. Its FastAPI/Starlette convenience layer
isn't present in this version (a lower-level protobuf/gRPC surface is),
and hand-assembling that layer wasn't worth the time against everything
else still to build. This client is the disclosed fallback: genuinely
separate services, real Agent Cards, real HTTP negotiation messages --
the substance PRD §17 asks for -- without a literal dependency on the
`a2a-sdk` package in its current form.
"""

from __future__ import annotations

import httpx

from pact.models.schemas import AgentCard, Offer, VendorId


class VendorUnavailableError(Exception):
    """Raised when a vendor service is unreachable (PRD §27)."""


class HttpVendorClient:
    # Must exceed the slowest real external call a vendor service makes
    # internally (AzurePricingClient's own httpx call to the live Azure
    # Retail Prices API uses a 30s timeout) -- otherwise this outer
    # client can time out while that legitimately-still-running inner
    # call would have succeeded, which is exactly what happened under
    # GitHub Actions' network latency to Azure's API (caught via a real
    # CI run, not assumed).
    def __init__(self, endpoints: dict[VendorId, str], timeout: float = 35.0):
        self._endpoints = endpoints
        self._timeout = timeout

    def get_agent_card(self, vendor_id: VendorId) -> AgentCard:
        url = f"{self._endpoints[vendor_id]}/.well-known/agent.json"
        try:
            resp = httpx.get(url, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise VendorUnavailableError(f"{vendor_id.value}: {exc}") from exc
        return AgentCard.model_validate(resp.json())

    def negotiate(
        self,
        vendor_id: VendorId,
        gpu_count: int,
        contract_months: int,
        round_number: int,
        max_rounds: int,
        claimed_discount_rate: float,
    ) -> Offer:
        url = f"{self._endpoints[vendor_id]}/negotiate"
        try:
            resp = httpx.post(
                url,
                params={
                    "gpu_count": gpu_count,
                    "contract_months": contract_months,
                    "round_number": round_number,
                    "max_rounds": max_rounds,
                    "claimed_discount_rate": claimed_discount_rate,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise VendorUnavailableError(f"{vendor_id.value}: {exc}") from exc
        return Offer.model_validate(resp.json())
