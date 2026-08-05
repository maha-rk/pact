"""Core data schemas shared across agents, vendors, logging, and the API.

These are the structured objects the PRD refers to throughout: the
requirement, offers/claims exchanged during negotiation, evidence items,
and the final Decision/Evidence/Reasoning output (FR-7). Every field here
is either user-supplied, computed, or fetched from a real external source
— nothing here is a slot for an invented value (PRD NFR "Accuracy of
grounding").
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """Structured procurement requirement (PRD FR-1)."""

    gpu_type: str
    gpu_count: int
    contract_months: int
    budget_ceiling_usd: float
    region: str | None = None
    raw_input: str = Field(description="The original text/transcript this was parsed from")


class VendorId(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    RUNPOD = "runpod"


class AgentCard(BaseModel):
    """A2A identity/capability declaration (PRD §17)."""

    vendor_id: VendorId
    name: str
    endpoint: str
    capabilities: list[str]
    certifications: list[str] = Field(default_factory=list)


class Offer(BaseModel):
    """One offer or counter-offer exchanged during negotiation."""

    vendor_id: VendorId
    round_number: int
    price_usd: float
    claimed_discount_rate: float | None = Field(
        default=None,
        description="A committed-use discount rate the vendor CLAIMS during "
        "negotiation. This is a negotiating position, not verified fact "
        "until the Verification Agent checks it against real pricing data.",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VerificationResult(BaseModel):
    """Result of checking one vendor claim against real external data."""

    vendor_id: VendorId
    claim_checked: str
    claimed_value: float
    actual_value: float
    source: str = Field(description="Where the real value came from, e.g. 'AWS Price List Bulk API'")
    matched: bool
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ComplianceResult(BaseModel):
    """Result of checking a candidate deal against policy constraints."""

    vendor_id: VendorId
    constraint_name: str
    passed: bool
    detail: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvidenceItem(BaseModel):
    """One piece of evidence backing a final decision (FR-7)."""

    label: str
    value: str
    source: str


class Decision(BaseModel):
    """The final Decision/Evidence/Reasoning output (FR-7). Never a bare
    confidence score — always evidence-backed reasoning."""

    negotiation_id: str
    selected_vendor: VendorId | None
    final_price_usd: float | None
    evidence: list[EvidenceItem]
    reasoning: str
    approved: bool = False
    approved_at: datetime | None = None


class PolicyConstraints(BaseModel):
    """Explicit policy configuration supplied ahead of a negotiation run."""

    budget_ceiling_usd: float
    blocked_vendors: list[VendorId] = Field(default_factory=list)
    required_certifications: list[str] = Field(default_factory=list)
