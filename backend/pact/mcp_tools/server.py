"""Real MCP server (PRD §24): exposes pricing_lookup and verify_claim as
genuine MCP protocol tools, backed by the same real AWS/Azure pricing
clients the live negotiation pipeline uses -- not a naming convention,
an actual server other MCP clients (Claude Desktop, other agents, etc.)
can discover and call over the real protocol.

Run standalone: python -m pact.mcp_tools.server
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from pact.models.schemas import Requirement, VendorId

app = MCPServer(
    name="pact-pricing-tools",
    version="0.1.0",
    instructions=(
        "Real-data tools backing Pact's Verification Agent: pricing_lookup "
        "fetches a vendor's real list price; verify_claim checks a claimed "
        "committed-use discount rate against real, live pricing data."
    ),
)


def _pricing_client(vendor_id: str):
    if vendor_id == "aws":
        from vendors.aws_vendor.pricing_client import AWSPricingClient

        return AWSPricingClient()
    if vendor_id == "azure":
        from vendors.azure_vendor.pricing_client import AzurePricingClient

        return AzurePricingClient()
    raise ValueError(f"No real pricing client wired for vendor '{vendor_id}' yet")


@app.tool(description="Fetch a vendor's real list price for a GPU compute requirement.")
def pricing_lookup(vendor_id: str, gpu_count: int, contract_months: int) -> dict:
    requirement = Requirement(
        gpu_type="H100", gpu_count=gpu_count, contract_months=contract_months, budget_ceiling_usd=0, raw_input=""
    )
    client = _pricing_client(vendor_id)
    return {
        "vendor_id": vendor_id,
        "list_price_usd": client.list_price(VendorId(vendor_id), requirement),
        "source": client.source_label(VendorId(vendor_id)),
    }


@app.tool(description="Verify a vendor's claimed committed-use discount rate against real, live pricing data.")
def verify_claim(vendor_id: str, claimed_discount_rate: float, gpu_count: int, contract_months: int) -> dict:
    requirement = Requirement(
        gpu_type="H100", gpu_count=gpu_count, contract_months=contract_months, budget_ceiling_usd=0, raw_input=""
    )
    client = _pricing_client(vendor_id)
    real_rate = client.real_committed_use_discount_rate(VendorId(vendor_id), requirement)
    return {
        "vendor_id": vendor_id,
        "claimed_discount_rate": claimed_discount_rate,
        "real_discount_rate": real_rate,
        "matched": claimed_discount_rate <= real_rate + 0.005,
        "source": client.source_label(VendorId(vendor_id)),
    }


if __name__ == "__main__":
    app.run()
