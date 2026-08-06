"""HTTP-based transport for the distributed Worker <-> standalone
Verification Agent service link -- the same real, separate-process
pattern already proven by the vendor agents (`pact/a2a/vendor_client.py`)
and the Compliance Agent (`pact/a2a/compliance_client.py`), applied to
the second of Pact's two feedback-loop agents.

No `plausibility_screener` parameter here: that's a Python callable in
the in-process API, and callables can't cross a process boundary. The
standalone Verification service resolves its own screener locally (see
`pact/services/verification_agent/app.py`), probing its own Ollama
instance exactly like the in-process path does."""

from __future__ import annotations

import httpx

from pact.models.schemas import Offer, Requirement, VerificationResult


class VerificationServiceUnavailableError(Exception):
    """Raised when the standalone Verification Agent service is unreachable."""


class HttpVerificationClient:
    def __init__(self, endpoint: str, timeout: float = 35.0):
        self._endpoint = endpoint
        self._timeout = timeout

    def verify(self, offer: Offer, requirement: Requirement) -> VerificationResult:
        url = f"{self._endpoint}/verify"
        body = {
            "offer": offer.model_dump(mode="json"),
            "requirement": requirement.model_dump(mode="json"),
        }
        try:
            resp = httpx.post(url, json=body, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise VerificationServiceUnavailableError(str(exc)) from exc
        return VerificationResult.model_validate(resp.json())
