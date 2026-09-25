"""
Enrichment Agent.

Responsibility (and ONLY this): take the founder's raw input, call the
MCP get_company_context tool, and merge both into a validated
CompanyProfile with clear provenance on every field (known / inferred).

This agent deliberately does NOT call an LLM. Merging structured data
and tagging its source is a deterministic operation — there's nothing
for a language model to "reason" about here, and using one would just
add latency and a hallucination risk for no benefit (see Section 29:
"Do not outsource deterministic business logic to the LLM"). The
genuinely agentic part of this step is the MCP tool call itself.

Does NOT perform board-gap analysis — that's the Analysis Agent's job.
"""
from app.models.schemas import (
    CompanyContext,
    CompanyProfile,
    FieldProvenance,
    FounderInput,
)
from app.services.mcp_client import call_get_company_context
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def enrichment_agent(founder_input: FounderInput) -> CompanyProfile:
    logger.info(f"Enrichment agent starting for '{founder_input.company_name}'")

    raw_context = await call_get_company_context(
        company_name=founder_input.company_name,
        website=founder_input.website,
        industry=founder_input.industry,
        stage=founder_input.stage,
    )
    company_context = CompanyContext(**raw_context)

    # Build provenance: anything the founder actually typed is "known".
    # Anything that came only from mock enrichment is "inferred".
    # Anything neither source gave us is "unknown".
    field_provenance: dict[str, FieldProvenance] = {}

    founder_fields = founder_input.model_dump(exclude_none=True)
    for field in founder_fields:
        field_provenance[field] = FieldProvenance.KNOWN

    context_fields = company_context.model_dump(exclude_none=True, exclude={"source"})
    for field in context_fields:
        if field not in field_provenance:
            field_provenance[field] = FieldProvenance.INFERRED

    profile = CompanyProfile(
        founder_input=founder_input,
        company_context=company_context,
        field_provenance=field_provenance,
    )

    logger.info(
        f"Enrichment agent complete for '{founder_input.company_name}' — "
        f"{len(field_provenance)} fields tracked"
    )
    return profile
