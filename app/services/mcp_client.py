"""
MCP client wrapper.

Launches mcp_server/server.py as a subprocess and talks to it over the
real MCP stdio protocol. This is the ONLY way agents should reach
enrichment data — never by importing mcp_server.tools directly
(see Section 7: "Agent → MCP client → MCP server → data provider").
"""
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).parent.parent.parent


async def call_get_company_context(
    company_name: str,
    website: str | None = None,
    industry: str | None = None,
    stage: str | None = None,
) -> dict:
    """
    Calls the get_company_context tool on the MCP server and returns
    the raw result dict. Raises if the MCP server is unreachable or
    the call fails — callers (the Enrichment Agent) are responsible
    for catching this and handling it gracefully (Section 18).
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_company_context",
                arguments={
                    "company_name": company_name,
                    "website": website,
                    "industry": industry,
                    "stage": stage,
                },
            )
            # Prefer structured_content when the server provides it;
            # otherwise fall back to parsing the text content block,
            # which is what our server currently returns (a JSON string).
            if result.structured_content:
                return result.structured_content

            for block in result.content:
                if getattr(block, "type", None) == "text":
                    return json.loads(block.text)

            raise RuntimeError(
                f"MCP tool call returned no usable content: {result}"
            )
