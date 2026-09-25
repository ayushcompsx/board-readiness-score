"""
MCP server for the Board Readiness Score project.

Exposes exactly one tool: `get_company_context`.

This is a genuine MCP tool boundary (Section 7 of the brief) — the
Enrichment Agent talks to this over the MCP protocol via an MCP client,
it never imports mock_data logic directly. That's what makes it easy to
swap this whole server for a real Crunchbase/LinkedIn/Companies House
integration later without touching the agent code.

Run standalone for local testing:
    python -m mcp_server.server
"""
from mcp.server.mcpserver import MCPServer

from mcp_server.tools.company_context import lookup_company_context

server = MCPServer(
    name="board-readiness-mcp",
    description="Provides mock company enrichment data for the "
    "Board Readiness Score agent pipeline.",
)


@server.tool()
def get_company_context(
    company_name: str,
    website: str | None = None,
    industry: str | None = None,
    stage: str | None = None,
) -> dict:
    """
    Look up enrichment context for a company.

    NOTE: this currently returns MOCK data (see mcp_server/data/companies.json).
    It simulates what a real provider integration would return, so the
    rest of the pipeline can be built against a stable, realistic shape.
    """
    return lookup_company_context(
        company_name=company_name,
        website=website,
        industry=industry,
        stage=stage,
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(server.run_stdio_async())
