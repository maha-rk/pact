"""Proves pact.mcp_tools.server is a real MCP server, not just tools shaped
like MCP -- spawns it as an actual subprocess and talks to it over the
real MCP stdio protocol via the official client SDK (PRD §24)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "pact.mcp_tools.server"],
    cwd=str(BACKEND_ROOT),
)


def _payload(result: CallToolResult) -> dict:
    """The real MCP wire payload for a plain-dict tool return is a text
    content block of JSON, not `structured_content` (that field stays
    unset without a declared output schema) -- parse the actual protocol
    response rather than a field that isn't populated here."""
    return json.loads(result.content[0].text)


async def test_real_mcp_server_lists_both_tools():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            names = {tool.name for tool in result.tools}
            assert names == {"pricing_lookup", "verify_claim"}


async def test_real_mcp_pricing_lookup_call_hits_real_aws_data():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "pricing_lookup", {"vendor_id": "aws", "gpu_count": 8, "contract_months": 3}
            )
            assert not result.is_error
            payload = _payload(result)
            assert payload["vendor_id"] == "aws"
            assert payload["list_price_usd"] == pytest.approx(118886.40, rel=1e-3)


async def test_real_mcp_verify_claim_call_catches_the_flagship_mismatch():
    """The real, live finding this whole build centers on: AWS has no
    sub-12-month committed-use tier, so a 25% claim on a 3-month contract
    is verifiably false -- proven here over the real MCP protocol, not an
    in-process function call."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "verify_claim",
                {"vendor_id": "aws", "claimed_discount_rate": 0.25, "gpu_count": 8, "contract_months": 3},
            )
            assert not result.is_error
            payload = _payload(result)
            assert payload["real_discount_rate"] == 0.0
            assert payload["matched"] is False
