"""
Report Generator Agent.

Responsibility (and ONLY this): take a validated BoardAnalysis and
produce the final founder-facing BoardReadinessReport.

Critical design constraint (Section 4 + 14): this agent must NOT
invent company facts. To enforce that structurally rather than just
by prompting, the LLM is only ever asked for NARRATIVE TEXT
(explanations, summary, next steps) — every actual fact (evidence,
suggested advisor profiles, the overall score, strengths) is copied
directly from the already-validated BoardAnalysis, never regenerated.
This means even if the LLM ignores an instruction, it structurally
cannot smuggle a new "fact" into the evidence/score fields, because
those fields never touch the LLM's output at all.
"""
import json
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from app.config.settings import settings
from app.models.schemas import BoardAnalysis, BoardReadinessReport, ReportGapSection
from app.services.llm_provider import get_llm
from app.utils.logging import get_logger

logger = get_logger(__name__)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "report" / "prompt.md"


class _LLMGapExplanation(BaseModel):
    dimension: str
    title: str
    why_it_matters: str


class _LLMReportOutput(BaseModel):
    executive_summary: str
    gap_explanations: list[_LLMGapExplanation]
    governance_current_signals: list[str]
    governance_improvements: list[str]
    recommended_next_steps: list[str]
    cta_text: str


class ReportAgentError(Exception):
    """Raised when the Report Agent cannot produce a valid result,
    even after retrying."""


def _build_prompt(analysis: BoardAnalysis, company_name: str) -> str:
    template = PROMPT_PATH.read_text()
    return template.format(
        board_analysis_json=analysis.model_dump_json(indent=2),
        company_name=company_name,
    )


def _parse_llm_response(raw_text: str) -> _LLMReportOutput:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return _LLMReportOutput(**data)


def _to_report(
    llm_output: _LLMReportOutput, analysis: BoardAnalysis
) -> BoardReadinessReport:
    """
    Merges LLM-written narrative with facts pulled directly from the
    validated analysis. This is where the "no invented facts" guarantee
    is structurally enforced, not just prompted for.
    """
    explanations_by_dimension = {
        exp.dimension: exp for exp in llm_output.gap_explanations
    }

    gap_sections = []
    for gap in analysis.gaps:
        explanation = explanations_by_dimension.get(gap.dimension.value)
        if explanation is None:
            # LLM skipped a gap it was given — fail loudly rather than
            # silently dropping a finding from the report.
            raise ValueError(
                f"LLM did not provide an explanation for gap dimension "
                f"'{gap.dimension.value}'"
            )
        gap_sections.append(
            ReportGapSection(
                title=explanation.title,
                why_it_matters=explanation.why_it_matters,
                evidence=gap.evidence,  # from analysis, not the LLM's report output
                suggested_advisor_profile=gap.suggested_advisor_profile,  # from analysis
            )
        )

    return BoardReadinessReport(
        overall_score=analysis.overall_score,  # from analysis, deterministic
        executive_summary=llm_output.executive_summary,
        strengths=analysis.strengths,  # from analysis, not regenerated
        gap_sections=gap_sections,
        governance_current_signals=llm_output.governance_current_signals,
        governance_improvements=llm_output.governance_improvements,
        recommended_next_steps=llm_output.recommended_next_steps,
        cta_text=llm_output.cta_text,
    )


async def report_agent(
    analysis: BoardAnalysis, company_name: str
) -> BoardReadinessReport:
    logger.info(f"Report agent starting for '{company_name}'")

    llm = get_llm(temperature=0.4)  # slightly higher — this step is about prose quality

    prompt = _build_prompt(analysis, company_name)
    max_attempts = 3  # see analysis.py for why this isn't 2

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            llm_output = _parse_llm_response(response.content)
            report = _to_report(llm_output, analysis)
            logger.info(
                f"Report agent complete for '{company_name}' (attempt {attempt})"
            )
            return report

        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_error = e
            logger.warning(f"Report agent attempt {attempt} produced invalid output: {e}")
            if attempt < max_attempts:
                prompt = (
                    prompt
                    + f"\n\nYour previous response was invalid: {e}\n"
                    + "Return ONLY valid JSON matching the required structure, "
                    + "with exactly one gap_explanations entry per gap in the input."
                )
                continue

        except Exception as e:
            # Timeouts / connection hiccups — worth retrying, not fatal
            # on the first sign of trouble (see analysis.py).
            last_error = e
            logger.warning(f"Report agent attempt {attempt} failed to reach the LLM: {e}")
            if attempt < max_attempts:
                continue

    raise ReportAgentError(
        f"Report agent failed after {max_attempts} attempts. Last error: {last_error}"
    )
