# Why this folder is empty

The Enrichment Agent (`app/agents/enrichment.py`) deliberately does not
call an LLM, so there's no prompt to define here.

Its job is: call the MCP `get_company_context` tool, then merge the
result with the founder's form input into a `CompanyProfile`. That's a
structured-data merge with a real tool call — there's no ambiguous
reasoning step that benefits from an LLM, and using one would only add
latency and a hallucination risk for zero benefit (see Section 29 of
the engineering brief: "Do not outsource deterministic business logic
to the LLM").

The genuinely agentic part of this step is the MCP tool call itself —
see `app/services/mcp_client.py` and `mcp_server/server.py`.
