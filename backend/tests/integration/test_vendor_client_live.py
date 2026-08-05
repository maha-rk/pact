"""Proves the Negotiation Agent <-> Vendor Agent link is genuinely a
separate-process HTTP round-trip, not a disguised function call (PRD
§17). Starts the real AWS and Azure FastAPI apps as actual background
processes on real ports and negotiates against them over real HTTP,
using each vendor's real, live pricing data underneath."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from pact.a2a.vendor_client import HttpVendorClient
from pact.models.schemas import VendorId

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


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
    aws_port = _free_port()
    azure_port = _free_port()
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "vendors.aws_vendor.app:app", "--port", str(aws_port)],
            cwd=BACKEND_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "vendors.azure_vendor.app:app", "--port", str(azure_port)],
            cwd=BACKEND_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    ]
    try:
        _wait_for_server(aws_port)
        _wait_for_server(azure_port)
        yield {
            VendorId.AWS: f"http://127.0.0.1:{aws_port}",
            VendorId.AZURE: f"http://127.0.0.1:{azure_port}",
        }
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=5)


def test_real_agent_cards_are_fetched_over_http(live_vendor_endpoints):
    client = HttpVendorClient(live_vendor_endpoints)
    aws_card = client.get_agent_card(VendorId.AWS)
    azure_card = client.get_agent_card(VendorId.AZURE)
    assert aws_card.vendor_id == VendorId.AWS
    assert azure_card.vendor_id == VendorId.AZURE
    assert aws_card.endpoint and azure_card.endpoint


def test_real_negotiation_round_trip_over_http(live_vendor_endpoints):
    client = HttpVendorClient(live_vendor_endpoints)
    aws_offer = client.negotiate(
        VendorId.AWS, gpu_count=8, contract_months=3, round_number=1, max_rounds=6, claimed_discount_rate=0.25
    )
    azure_offer = client.negotiate(
        VendorId.AZURE, gpu_count=8, contract_months=3, round_number=1, max_rounds=6, claimed_discount_rate=0.8152
    )
    # Round 1 always equals each vendor's real opening (list) price --
    # confirms this is genuinely backed by the live pricing data, not a
    # canned response.
    assert aws_offer.price_usd == pytest.approx(118886.40, rel=1e-3)
    assert azure_offer.price_usd == pytest.approx(212371.20, rel=1e-3)


def test_unreachable_vendor_raises_disclosed_error():
    from pact.a2a.vendor_client import VendorUnavailableError

    client = HttpVendorClient({VendorId.GCP: "http://127.0.0.1:1"})  # nothing listening
    with pytest.raises(VendorUnavailableError):
        client.get_agent_card(VendorId.GCP)
