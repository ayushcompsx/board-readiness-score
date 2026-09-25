"""
Analysis Agent.

Responsibility (and ONLY this): take a CompanyProfile and produce a
structured BoardAnalysis — dimension-by-dimension maturity assessment,
capability gaps, and strengths.

Does NOT write the final founder-facing report — that's the Report
Generator Agent's job.

Design notes:
- The LLM outputs QUALITATIVE maturity labels per dimension (Section 10),
  never a raw numeric score — the score is calculated deterministically
  by app.scoring.board_readiness from those labels.
- If the LLM returns invalid/malformed JSON, we retry ONCE with a
  stricter reminder, then raise a clear error rather than silently
  accepting bad output (Section 5).
- Requires Ollama running locally. If Ollama is unreachable, this
  raises a clear, actionable error rather than an opaque stack trace.
"""
import json
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from app.config.settings import settings
from app.models.schemas import (
    BoardAnalysis,
    CapabilityGap,
    CompanyProfile,
    DimensionName,
    DimensionScore,
)
from app.scoring.board_readiness import calculate_overall_score, score_from_maturity_label
from app.services.llm_provider import get_llm
from app.utils.logging import get_logger

logger = get_logger(__name__)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "analysis" / "prompt.md"


# --- Internal schemas for RAW LLM output, before conversion into the
# --- shared BoardAnalysis contract. These never leave this file.

class _LLMDimensionAssessment(BaseModel):
    dimension: str
    maturity_label: Literal["strong", "adequate", "emerging", "absent"]
    evidence: list[str]
    confidence: Literal["low", "medium", "high"] = "medium"


class _LLMGap(BaseModel):
    dimension: str
    severity: Literal["low", "medium", "high"]
    evidence: list[str]
    confidence: Literal["low", "medium", "high"] = "medium"
    suggested_advisor_profile: str


class _LLMAnalysisOutput(BaseModel):
    dimension_assessments: list[_LLMDimensionAssessment]
    gaps: list[_LLMGap]
    strengths: list[str]


class AnalysisAgentError(Exception):
    """Raised when the Analysis Agent cannot produce a valid result,
    even after retrying — e.g. Ollama unreachable, or the model
    repeatedly returns malformed output."""


def _build_prompt(profile: CompanyProfile) -> str:
    template = PROMPT_PATH.read_text()
    return template.format(
        company_profile_json=profile.model_dump_json(indent=2)
    )


def _parse_llm_response(raw_text: str) -> _LLMAnalysisOutput:
    """
    Parses and validates the LLM's raw text response. Raises
    ValueError/ValidationError on any problem — caller decides
    whether to retry.
    """
    # Models sometimes wrap JSON in ```json fences despite instructions —
    # strip that defensively rather than failing on an easy case.
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)  # raises json.JSONDecodeError on bad JSON
    return _LLMAnalysisOutput(**data)  # raises ValidationError on bad shape


def _to_board_analysis(llm_output: _LLMAnalysisOutput) -> BoardAnalysis:
    """Converts validated raw LLM output into the shared BoardAnalysis
    contract, computing scores deterministically."""
    dimension_scores = []
    for assessment in llm_output.dimension_assessments:
        try:
            dim_name = DimensionName(assessment.dimension)
        except ValueError:
            raise ValueError(
                f"LLM returned unrecognised dimension name: '{assessment.dimension}'"
            )
        dimension_scores.append(
            DimensionScore(
                name=dim_name,
                score=score_from_maturity_label(assessment.maturity_label),
                evidence=assessment.evidence,
                confidence=assessment.confidence,
            )
        )

    overall_score = calculate_overall_score(dimension_scores)

    gaps = []
    for gap in llm_output.gaps:
        try:
            dim_name = DimensionName(gap.dimension)
        except ValueError:
            raise ValueError(f"LLM returned unrecognised gap dimension: '{gap.dimension}'")
        gaps.append(
            CapabilityGap(
                dimension=dim_name,
                severity=gap.severity,
                evidence=gap.evidence,
                confidence=gap.confidence,
                suggested_advisor_profile=gap.suggested_advisor_profile,
            )
        )

    return BoardAnalysis(
        dimension_scores=dimension_scores,
        gaps=gaps,
        strengths=llm_output.strengths,
        overall_score=overall_score,
    )


async def analysis_agent(profile: CompanyProfile) -> BoardAnalysis:
    logger.info(
        f"Analysis agent starting for '{profile.founder_input.company_name}'"
    )

    llm = get_llm(temperature=0.2)  # low temperature — assessment, not creative writing

    prompt = _build_prompt(profile)
    max_attempts = 3  # bumped from 2: a slow-but-working call (common on
    # constrained local hardware) should get a real second chance, not
    # just malformed-JSON retries

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            llm_output = _parse_llm_response(response.content)
            analysis = _to_board_analysis(llm_output)
            logger.info(
                f"Analysis agent complete for '{profile.founder_input.company_name}' "
                f"— overall score {analysis.overall_score} (attempt {attempt})"
            )
            return analysis

        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            # Model responded, but with bad content — retry with a
            # stricter reminder appended.
            last_error = e
            logger.warning(
                f"Analysis agent attempt {attempt} produced invalid output: {e}"
            )
            if attempt < max_attempts:
                prompt = (
                    prompt
                    + "\n\nYour previous response was invalid: "
                    + f"{e}\nReturn ONLY valid JSON matching the required structure."
                )
                continue

        except Exception as e:
            # Covers timeouts, connection hiccups, slow model loads on
            # constrained hardware, etc. These ARE worth retrying — a
            # slow response isn't the same as Ollama being fundamentally
            # unreachable. We only give up after exhausting max_attempts.
            last_error = e
            logger.warning(
                f"Analysis agent attempt {attempt} failed to reach the LLM: {e}"
            )
            if attempt < max_attempts:
                continue

    raise AnalysisAgentError(
        f"Analysis agent failed after {max_attempts} attempts "
        f"(provider: {settings.model_provider}). Last error: {last_error}"
    )
