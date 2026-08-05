"""API-level integration test: drives the full flagship scenario through
the real pact-core FastAPI app exactly as the frontend/demo will, against
the real AWS and Azure vendor services running as separate processes."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

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
def app_client():
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

        import pact.api.routes_negotiation as routes

        routes.VENDOR_ENDPOINTS[routes.VendorId.AWS] = f"http://127.0.0.1:{aws_port}"
        routes.VENDOR_ENDPOINTS[routes.VendorId.AZURE] = f"http://127.0.0.1:{azure_port}"
        routes.AGENT_CARDS = {
            vid: routes.AgentCard(vendor_id=vid, name=f"{vid.value} vendor", endpoint=ep, capabilities=["negotiate"])
            for vid, ep in routes.VENDOR_ENDPOINTS.items()
        }

        from pact.main import app

        with TestClient(app) as client:
            yield client
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=5)


def test_full_negotiation_lifecycle_over_the_real_api(app_client):
    create_resp = app_client.post(
        "/negotiations",
        json={
            "gpu_count": 8,
            "contract_months": 3,
            "budget_ceiling_usd": 115000.0,
            "raw_input": "Need 8 H100 GPUs, 3-month contract, $115,000 budget",
            "initial_claimed_discounts": {"aws": 0.25, "azure": 0.8152},
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["status"] == "agreed_pending_approval"
    assert created["decision"]["selected_vendor"] == "azure"
    negotiation_id = created["negotiation_id"]

    get_resp = app_client.get(f"/negotiations/{negotiation_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert len(fetched["events"]) > 0
    assert fetched["decision"]["approved"] is False

    approve_resp = app_client.post(f"/negotiations/{negotiation_id}/approve", json={"approved_by": "pytest"})
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "finalized"
    assert approved["decision"]["approved"] is True

    # Re-approving is rejected -- FR-8's finalization boundary.
    second_approve = app_client.post(f"/negotiations/{negotiation_id}/approve", json={"approved_by": "pytest"})
    assert second_approve.status_code == 409


def test_unknown_negotiation_returns_404(app_client):
    resp = app_client.get("/negotiations/does-not-exist")
    assert resp.status_code == 404
