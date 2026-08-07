"""HTTP-based transport for the distributed Worker <-> standalone
Compliance Agent service link -- the same real, separate-process pattern
already proven by the vendor agents (`pact/a2a/vendor_client.py`),
applied to one of Pact's own internal agents to prove it can be
independently deployed and scaled too, not just the external vendors.

Structurally identical to `HttpVendorClient`: plain HTTP/JSON, no
`a2a-sdk` dependency (same disclosed scope note as `vendor_client.py`),
one real service per link."""

from __future__ import annotations

import httpx

from pact.models.schemas import ComplianceResult, Offer, PolicyConstraints


class ComplianceServiceUnavailableError(Exception):
    """Raised when the standalone Compliance Agent service is unreachable."""


class HttpComplianceClient:
    def __init__(self, endpoint: str, timeout: float = 35.0):
        self._endpoint = endpoint
        self._timeout = timeout

    def check_compliance(
        self,
        offer: Offer,
        policy: PolicyConstraints,
        vendor_certifications: list[str] | None = None,
        vendor_renewable_energy_pct: float | None = None,
    ) -> ComplianceResult:
        url = f"{self._endpoint}/check-compliance"
        body = {
            "offer": offer.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "vendor_certifications": vendor_certifications or [],
            "vendor_renewable_energy_pct": vendor_renewable_energy_pct,
        }
        try:
            resp = httpx.post(url, json=body, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ComplianceServiceUnavailableError(str(exc)) from exc
        return ComplianceResult.model_validate(resp.json())
