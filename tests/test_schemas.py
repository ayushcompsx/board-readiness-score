"""Tests for Pydantic data contracts (Section 5, 20)."""
import pytest
from pydantic import ValidationError

from app.models.schemas import (
    CompanyContext,
    DimensionScore,
    FounderInput,
    DimensionName,
)


class TestFounderInput:
    def test_minimal_valid_input(self):
        f = FounderInput(
            company_name="Acme", stage="Seed", industry="Fintech", team_size=5
        )
        assert f.company_name == "Acme"
        assert f.website is None  # optional fields default to None

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            FounderInput(stage="Seed", industry="Fintech", team_size=5)  # no company_name


class TestCompanyContext:
    def test_defaults_to_mock_source(self):
        c = CompanyContext()
        assert c.source == "mock"

    def test_all_fields_optional_except_source(self):
        # Should not raise even with nothing provided
        c = CompanyContext()
        assert c.description is None


class TestDimensionScore:
    def test_score_must_be_0_to_100(self):
        with pytest.raises(ValidationError):
            DimensionScore(
                name=DimensionName.LEADERSHIP_DEPTH, score=150, evidence=["e"]
            )
        with pytest.raises(ValidationError):
            DimensionScore(
                name=DimensionName.LEADERSHIP_DEPTH, score=-5, evidence=["e"]
            )

    def test_valid_score_boundaries(self):
        low = DimensionScore(name=DimensionName.LEADERSHIP_DEPTH, score=0, evidence=["e"])
        high = DimensionScore(name=DimensionName.LEADERSHIP_DEPTH, score=100, evidence=["e"])
        assert low.score == 0
        assert high.score == 100
