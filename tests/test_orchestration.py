"""
Tests for the pipeline orchestrator (Section 18, 19, 20).

Uses mocked agents so these tests run fast and don't depend on a real
Ollama instance being available — that's what proves the ORCHESTRATION
logic works, independent of any specific agent's LLM behaviour.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.models.schemas import (
    AssessmentStatus,
    BoardAnalysis,
    BoardReadinessReport,
    CompanyContext,
    CompanyProfile,
    DimensionName,
    DimensionScore,
    FounderInput,
)
from app.orchestration.pipeline import run_assessment


def _make_founder_input():
    return FounderInput(
        company_name="TestCo", stage="Seed", industry="Fintech", team_size=10
    )


def _make_profile(founder_input):
    return CompanyProfile(
        founder_input=founder_input,
        company_context=CompanyContext(description="mock"),
        field_provenance={},
    )


def _make_analysis():
    scores = [
        DimensionScore(name=d, score=50, evidence=["e"]) for d in DimensionName
    ]
    return BoardAnalysis(dimension_scores=scores, gaps=[], strengths=["s"], overall_score=50)


def _make_report():
    return BoardReadinessReport(
        overall_score=50,
        executive_summary="summary",
        strengths=["s"],
        gap_sections=[],
        governance_current_signals=[],
        governance_improvements=[],
        recommended_next_steps=["a", "b", "c"],
    )


class TestPipelineHappyPath:
    @pytest.mark.asyncio
    async def test_full_pipeline_runs_all_stages(self):
        founder_input = _make_founder_input()
        profile = _make_profile(founder_input)
        analysis = _make_analysis()
        report = _make_report()

        with patch(
            "app.orchestration.pipeline.enrichment_agent", new=AsyncMock(return_value=profile)
        ), patch(
            "app.orchestration.pipeline.analysis_agent", new=AsyncMock(return_value=analysis)
        ), patch(
            "app.orchestration.pipeline.report_agent", new=AsyncMock(return_value=report)
        ):
            run = await run_assessment(founder_input)

        assert run.status == AssessmentStatus.COMPLETE
        assert run.company_profile is not None
        assert run.board_analysis is not None
        assert run.report is not None
        assert run.lead_score is not None
        assert len(run.run_metadata) == 3
        assert all(m.success for m in run.run_metadata)

    @pytest.mark.asyncio
    async def test_assessment_id_is_unique_per_run(self):
        founder_input = _make_founder_input()
        profile = _make_profile(founder_input)
        analysis = _make_analysis()
        report = _make_report()

        with patch(
            "app.orchestration.pipeline.enrichment_agent", new=AsyncMock(return_value=profile)
        ), patch(
            "app.orchestration.pipeline.analysis_agent", new=AsyncMock(return_value=analysis)
        ), patch(
            "app.orchestration.pipeline.report_agent", new=AsyncMock(return_value=report)
        ):
            run1 = await run_assessment(founder_input)
            run2 = await run_assessment(founder_input)

        assert run1.assessment_id != run2.assessment_id


class TestPipelineFailureHandling:
    @pytest.mark.asyncio
    async def test_enrichment_failure_stops_pipeline_early(self):
        founder_input = _make_founder_input()

        with patch(
            "app.orchestration.pipeline.enrichment_agent",
            new=AsyncMock(side_effect=RuntimeError("MCP unreachable")),
        ):
            run = await run_assessment(founder_input)

        assert run.status == AssessmentStatus.FAILED
        assert run.company_profile is None
        assert run.board_analysis is None
        assert len(run.run_metadata) == 1
        assert run.run_metadata[0].success is False

    @pytest.mark.asyncio
    async def test_analysis_failure_preserves_enrichment_result(self):
        """A later-stage failure should not throw away earlier valid
        work — the founder's profile is still there even if analysis
        couldn't complete."""
        founder_input = _make_founder_input()
        profile = _make_profile(founder_input)

        with patch(
            "app.orchestration.pipeline.enrichment_agent", new=AsyncMock(return_value=profile)
        ), patch(
            "app.orchestration.pipeline.analysis_agent",
            new=AsyncMock(side_effect=RuntimeError("Ollama unreachable")),
        ):
            run = await run_assessment(founder_input)

        assert run.status == AssessmentStatus.FAILED
        assert run.company_profile is not None  # preserved
        assert run.board_analysis is None
        assert run.run_metadata[0].success is True  # enrichment
        assert run.run_metadata[1].success is False  # analysis

    @pytest.mark.asyncio
    async def test_report_failure_preserves_analysis_result(self):
        founder_input = _make_founder_input()
        profile = _make_profile(founder_input)
        analysis = _make_analysis()

        with patch(
            "app.orchestration.pipeline.enrichment_agent", new=AsyncMock(return_value=profile)
        ), patch(
            "app.orchestration.pipeline.analysis_agent", new=AsyncMock(return_value=analysis)
        ), patch(
            "app.orchestration.pipeline.report_agent",
            new=AsyncMock(side_effect=RuntimeError("Report generation failed")),
        ):
            run = await run_assessment(founder_input)

        assert run.status == AssessmentStatus.FAILED
        assert run.board_analysis is not None  # preserved
        assert run.report is None
