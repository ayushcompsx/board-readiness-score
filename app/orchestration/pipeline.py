"""
Pipeline orchestrator.

Runs: Enrichment -> Analysis -> Report -> Lead Scoring, in sequence,
against a single AssessmentRun. Tracks per-agent timing/success in
run_metadata (Section 19: observability) and fails gracefully at
whichever stage breaks, rather than crashing (Section 18).

This is intentionally a straight-line pipeline, not a looping agent —
per Section 23: "A good agentic architecture is not 'LLM calls itself
20 times.' A good architecture is: each agent has a clear
responsibility and a clear stopping condition."
"""
import time
from datetime import UTC, datetime

from app.agents.analysis import AnalysisAgentError, analysis_agent
from app.agents.enrichment import enrichment_agent
from app.agents.report import ReportAgentError, report_agent
from app.models.schemas import (
    AgentRunMetadata,
    AssessmentRun,
    AssessmentStatus,
    FounderInput,
)
from app.scoring.lead_score import calculate_lead_score
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def _run_stage(run: AssessmentRun, agent_name: str, coro):
    """
    Runs one agent stage, records timing/success/failure metadata on
    the AssessmentRun, and re-raises any exception after recording it
    (the caller decides how to handle a failed stage).
    """
    started_at = datetime.now(UTC)
    start = time.perf_counter()
    try:
        result = await coro
        duration_ms = (time.perf_counter() - start) * 1000
        run.run_metadata.append(
            AgentRunMetadata(
                agent_name=agent_name,
                started_at=started_at,
                duration_ms=duration_ms,
                success=True,
            )
        )
        logger.info(
            f"[{run.assessment_id}] {agent_name} succeeded in {duration_ms:.0f}ms"
        )
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        run.run_metadata.append(
            AgentRunMetadata(
                agent_name=agent_name,
                started_at=started_at,
                duration_ms=duration_ms,
                success=False,
                validation_errors=[str(e)],
            )
        )
        logger.error(
            f"[{run.assessment_id}] {agent_name} failed after {duration_ms:.0f}ms: {e}"
        )
        raise


async def run_assessment(founder_input: FounderInput) -> AssessmentRun:
    """
    Runs the full pipeline for one founder submission. Always returns
    an AssessmentRun — even on failure, status will be FAILED and
    run_metadata will show exactly which stage broke and why, rather
    than raising an unhandled exception up to the API layer.
    """
    run = AssessmentRun(founder_input=founder_input, status=AssessmentStatus.RUNNING)
    logger.info(
        f"[{run.assessment_id}] Starting assessment for "
        f"'{founder_input.company_name}'"
    )

    try:
        run.company_profile = await _run_stage(
            run, "enrichment_agent", enrichment_agent(founder_input)
        )
    except Exception:
        run.status = AssessmentStatus.FAILED
        return run

    try:
        run.board_analysis = await _run_stage(
            run, "analysis_agent", analysis_agent(run.company_profile)
        )
    except (AnalysisAgentError, Exception):
        run.status = AssessmentStatus.FAILED
        return run

    try:
        run.report = await _run_stage(
            run,
            "report_agent",
            report_agent(run.board_analysis, founder_input.company_name),
        )
    except (ReportAgentError, Exception):
        run.status = AssessmentStatus.FAILED
        return run

    # Lead scoring is deterministic — no need to wrap in the same
    # try/except pattern used for LLM-backed stages, but we still
    # guard it so a bug here doesn't lose an otherwise-complete report.
    try:
        run.lead_score = calculate_lead_score(run.company_profile, run.board_analysis)
    except Exception as e:
        logger.error(f"[{run.assessment_id}] Lead scoring failed: {e}")
        # Report is still valid and usable even without a lead score,
        # so we don't fail the whole run for this.
        run.lead_score = None

    run.status = AssessmentStatus.COMPLETE
    logger.info(f"[{run.assessment_id}] Assessment complete")
    return run
