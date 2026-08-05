"""The ultimate proof point: the full Flagship Demonstration Scenario run
through the real 6-agent pipeline, negotiating over real HTTP against the
AWS and Azure vendor services running as genuinely separate OS processes,
using each vendor's real, live pricing data. Not fixtures, not mocks --
this is what the live demo actually does end to end."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from pact.a2a.vendor_client import HttpVendorClient
from pact.models.schemas import AgentCard, PolicyConstraints, Requirement, VendorId
from pact.orchestration import approval
from pact.orchestration.graph import run_negotiation
from pact.orchestration.state import EventType, NegotiationStatus
from vendors.aws_vendor.pricing_client import AWSPricingClient
from vendors.azure_vendor.pricing_client import AzurePricingClient

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
CANDIDATE_VENDORS = [VendorId.AWS, VendorId.AZURE]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(f"http://127.0.0.1:{port}/.well-known/agent.json", timeout=1.0)
            return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError(f"Server on port {port} did not start in time")


@pytest.fixture(scope="module")
def live_vendor_endpoints():
    aws_port, azure_port = _free_port(), _free_port()
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "vendors.aws_vendor.app:app", "--port", str(aws_port)],
            cwd=BACKEND_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ),
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "vendors.azure_vendor.app:app", "--port", str(azure_port)],
            cwd=BACKEND_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ),
    ]
    try:
        _wait_for_server(aws_port)
        _wait_for_server(azure_port)
        yield {VendorId.AWS: f"http://127.0.0.1:{aws_port}", VendorId.AZURE: f"http://127.0.0.1:{azure_port}"}
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=5)


class _CombinedPricingSource:
    """Verification's independent data source: the same real pricing
    clients the vendor services use, called directly by the orchestrator
    -- an independent check, not a re-read of the vendor's own claim."""

    def __init__(self):
        self._aws = AWSPricingClient()
        self._azure = AzurePricingClient()

    def list_price(self, vendor_id, requirement):
        return (self._aws if vendor_id == VendorId.AWS else self._azure).list_price(vendor_id, requirement)

    def real_committed_use_discount_rate(self, vendor_id, requirement):
        client = self._aws if vendor_id == VendorId.AWS else self._azure
        return client.real_committed_use_discount_rate(vendor_id, requirement)

    def source_label(self, vendor_id):
        return (self._aws if vendor_id == VendorId.AWS else self._azure).source_label(vendor_id)


def test_flagship_scenario_over_real_http_against_real_vendor_processes(live_vendor_endpoints):
    vendor_client = HttpVendorClient(live_vendor_endpoints)
    agent_cards = {
        VendorId.AWS: AgentCard(vendor_id=VendorId.AWS, name="AWS Vendor Agent", endpoint=live_vendor_endpoints[VendorId.AWS], capabilities=["negotiate"]),
        VendorId.AZURE: AgentCard(vendor_id=VendorId.AZURE, name="Azure Vendor Agent", endpoint=live_vendor_endpoints[VendorId.AZURE], capabilities=["negotiate"]),
    }
    requirement = Requirement(
        gpu_type="H100", gpu_count=8, contract_months=3, budget_ceiling_usd=115000.0,
        raw_input="Need 8 H100 GPUs, 3-month contract, $115,000 budget",
    )
    policy = PolicyConstraints(budget_ceiling_usd=115000.0)

    state = run_negotiation(
        requirement=requirement,
        policy=policy,
        candidate_vendors=CANDIDATE_VENDORS,
        agent_cards=agent_cards,
        pricing_source=_CombinedPricingSource(),
        initial_claimed_discounts={VendorId.AWS: 0.25, VendorId.AZURE: 0.8152},
        vendor_client=vendor_client,
    )

    # Wow moment #1, over real HTTP against the real AWS service.
    aws_rejections = [r for r in state.verification_results if r.vendor_id == VendorId.AWS and not r.matched]
    assert aws_rejections, "AWS's claim must be caught even when negotiated over real HTTP"
    assert aws_rejections[0].actual_value == 0.0

    # Wow moment #2: a verified offer still rejected on compliance grounds.
    compliance_rejections = [c for c in state.compliance_results if not c.passed]
    assert compliance_rejections

    # The system converges on a real, compliant, HTTP-negotiated deal.
    assert state.status == NegotiationStatus.AGREED_PENDING_APPROVAL
    assert state.decision.selected_vendor == VendorId.AZURE
    assert state.decision.final_price_usd <= policy.budget_ceiling_usd

    approval.approve(state, approved_by="live-integration-test")
    assert state.status == NegotiationStatus.FINALIZED
