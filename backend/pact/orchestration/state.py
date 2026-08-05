"""Negotiation state and the event log that backs both the replay UI
(FR-10) and the evaluation harness (§29) — one real record, queried two
ways (§25)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from pact.models.schemas import (
    ComplianceResult,
    Decision,
    Offer,
    PolicyConstraints,
    Requirement,
    VendorId,
    VerificationResult,
)


class EventType(str, Enum):
    REQUIREMENT_RECEIVED = "requirement_received"
    VENDOR_DISCOVERED = "vendor_discovered"
    OFFER_MADE = "offer_made"
    CLAIM_VERIFIED = "claim_verified"
    CLAIM_REJECTED = "claim_rejected"
    RENEGOTIATION_TRIGGERED = "renegotiation_triggered"
    COMPLIANCE_PASSED = "compliance_passed"
    COMPLIANCE_REJECTED = "compliance_rejected"
    DECISION_PRODUCED = "decision_produced"
    DECISION_APPROVED = "decision_approved"
    NO_COMPLIANT_DEAL = "no_compliant_deal"
    VENDOR_UNAVAILABLE = "vendor_unavailable"


class NegotiationEvent(BaseModel):
    """One timestamped entry in the negotiation log (FR-9)."""

    event_type: EventType
    vendor_id: VendorId | None = None
    round_number: int | None = None
    detail: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NegotiationStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    AGREED_PENDING_APPROVAL = "agreed_pending_approval"
    FINALIZED = "finalized"
    NO_COMPLIANT_DEAL = "no_compliant_deal"


class NegotiationState(BaseModel):
    """The full, queryable state of one negotiation run."""

    negotiation_id: str
    requirement: Requirement
    policy: PolicyConstraints
    status: NegotiationStatus = NegotiationStatus.IN_PROGRESS
    active_vendors: list[VendorId] = Field(default_factory=list)
    unavailable_vendors: list[VendorId] = Field(default_factory=list)
    offers: list[Offer] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    compliance_results: list[ComplianceResult] = Field(default_factory=list)
    events: list[NegotiationEvent] = Field(default_factory=list)
    decision: Decision | None = None

    def log(self, event_type: EventType, detail: str, vendor_id: VendorId | None = None,
            round_number: int | None = None) -> None:
        self.events.append(
            NegotiationEvent(
                event_type=event_type,
                vendor_id=vendor_id,
                round_number=round_number,
                detail=detail,
            )
        )

    def offers_for(self, vendor_id: VendorId) -> list[Offer]:
        return [o for o in self.offers if o.vendor_id == vendor_id]

    def latest_offer_for(self, vendor_id: VendorId) -> Offer | None:
        vendor_offers = self.offers_for(vendor_id)
        return vendor_offers[-1] if vendor_offers else None
