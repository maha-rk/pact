"""MCP tool: pricing_lookup. Wraps each vendor's real pricing data behind
one consistent interface every agent calls through (PRD §24). Fixture and
live implementations both satisfy this Protocol."""

from __future__ import annotations

from typing import Protocol

from pact.models.schemas import Requirement, VendorId


class PricingSource(Protocol):
    def list_price(self, vendor_id: VendorId, requirement: Requirement) -> float:
        """The vendor's real, undiscounted sticker price for this requirement."""
        ...

    def real_committed_use_discount_rate(self, vendor_id: VendorId, requirement: Requirement) -> float:
        """The real, currently-published committed-use discount rate for
        this vendor and contract length -- the ground truth the
        Verification Agent checks negotiating claims against."""
        ...

    def source_label(self, vendor_id: VendorId) -> str:
        """Human-readable citation for where this data actually came from."""
        ...
