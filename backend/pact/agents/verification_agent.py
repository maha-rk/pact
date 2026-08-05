"""Verification Agent: independently checks every vendor claim against real
external data before it can affect the outcome (PRD FR-5, §17). The
pass/fail verdict is a plain deterministic comparison -- never an LLM
judgment call. Self-hosted Gemma pre-screens high-frequency extraction in
the live-data path (see pact/models/gemma_client.py); the match/mismatch
decision itself always happens here, deterministically."""

from __future__ import annotations

from pact.mcp_tools.pricing_tool import PricingSource
from pact.mcp_tools.verification_tool import verify_claim
from pact.models.schemas import Offer, Requirement, VerificationResult


def verify(offer: Offer, requirement: Requirement, pricing_source: PricingSource) -> VerificationResult:
    return verify_claim(offer, requirement, pricing_source)
