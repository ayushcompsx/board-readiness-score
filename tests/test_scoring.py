"""
Tests for deterministic scoring (Section 10, 13, 20).

These are the most important tests in the repo: the scoring logic is
the one place we explicitly chose determinism over LLM output, and
that guarantee is only real if it's tested.
"""
import pytest

from app.models.schemas import (
    CapabilityGap,
    CompanyContext,
    CompanyProfile,
    DimensionName,
    DimensionScore,
    FounderInput,
)
from app.scoring.board_readiness import (
    calculate_overall_score,
    score_from_maturity_label,
)
from app.scoring.lead_score import calculate_lead_score


class TestBoardReadinessScoring:
    def test_maturity_label_conversion(self):
        assert score_from_maturity_label("strong") == 85
        assert score_from_maturity_label("adequate") == 60
        assert score_from_maturity_label("emerging") == 35
        assert score_from_maturity_label("absent") == 10

    def test_maturity_label_case_insensitive(self):
        assert score_from_maturity_label("STRONG") == 85
        assert score_from_maturity_label("  strong  ") == 85

    def test_invalid_maturity_label_raises(self):
        with pytest.raises(ValueError):
            score_from_maturity_label("excellent")

    def test_overall_score_equal_weighted_average(self):
        scores = [
            DimensionScore(name=d, score=60, evidence=["e"])
            for d in DimensionName
        ]
        assert calculate_overall_score(scores) == 60

    def test_overall_score_missing_dimension_raises(self):
        scores = [
            DimensionScore(name=d, score=60, evidence=["e"])
            for d in list(DimensionName)[:-1]  # missing one
        ]
        with pytest.raises(ValueError, match="Missing scores"):
            calculate_overall_score(scores)

    def test_overall_score_empty_raises(self):
        with pytest.raises(ValueError):
            calculate_overall_score([])

    def test_overall_score_is_deterministic(self):
        """Same input must always produce the same output — this is
        the core guarantee that makes the score explainable."""
        scores = [
            DimensionScore(name=d, score=score_from_maturity_label("adequate"), evidence=["e"])
            for d in DimensionName
        ]
        result1 = calculate_overall_score(scores)
        result2 = calculate_overall_score(scores)
        assert result1 == result2 == 60


class TestLeadScoring:
    def _make_profile(self, stage="Series A", team_size=35, areas_seeking_expertise=None):
        f = FounderInput(
            company_name="TestCo",
            stage=stage,
            industry="Fintech",
            team_size=team_size,
            areas_seeking_expertise=areas_seeking_expertise,
        )
        c = CompanyContext(description="mock")
        return CompanyProfile(founder_input=f, company_context=c, field_provenance={})

    def _make_analysis(self, gaps=None, governance_score=50):
        scores = [
            DimensionScore(
                name=d,
                score=governance_score if d.value == "Governance maturity" else 60,
                evidence=["e"],
            )
            for d in DimensionName
        ]
        return_gaps = gaps or []
        from app.models.schemas import BoardAnalysis
        return BoardAnalysis(
            dimension_scores=scores,
            gaps=return_gaps,
            strengths=["strength"],
            overall_score=55,
        )

    def test_strong_lead_signals_produce_hot_tier(self):
        profile = self._make_profile(
            stage="Series A", team_size=35, areas_seeking_expertise="Need a CFO"
        )
        gaps = [
            CapabilityGap(
                dimension=DimensionName.FINANCIAL_OVERSIGHT,
                severity="high",
                evidence=["e"],
                suggested_advisor_profile="CFO",
            )
        ]
        analysis = self._make_analysis(gaps=gaps, governance_score=20)
        lead = calculate_lead_score(profile, analysis)
        assert lead.tier.value == "hot"
        assert lead.score >= 70

    def test_weak_lead_signals_produce_low_tier(self):
        profile = self._make_profile(stage="Pre-seed", team_size=2)
        analysis = self._make_analysis(gaps=[], governance_score=80)
        lead = calculate_lead_score(profile, analysis)
        assert lead.tier.value == "low"

    def test_lead_score_capped_at_100(self):
        profile = self._make_profile(
            stage="Series A", team_size=50, areas_seeking_expertise="Everything"
        )
        gaps = [
            CapabilityGap(
                dimension=d, severity="high", evidence=["e"], suggested_advisor_profile="x"
            )
            for d in list(DimensionName)[:5]
        ]
        analysis = self._make_analysis(gaps=gaps, governance_score=10)
        lead = calculate_lead_score(profile, analysis)
        assert lead.score <= 100

    def test_lead_score_signals_are_explainable(self):
        """Every point awarded should be traceable to a listed signal —
        this is what makes the score explainable, not a black box."""
        profile = self._make_profile(stage="Seed", team_size=15)
        analysis = self._make_analysis(gaps=[], governance_score=60)
        lead = calculate_lead_score(profile, analysis)
        assert len(lead.signals) > 0
        assert any("Stage" in s for s in lead.signals)
