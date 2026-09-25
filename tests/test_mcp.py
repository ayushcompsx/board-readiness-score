"""Tests for the MCP company enrichment tool (Section 6, 20)."""
from mcp_server.tools.company_context import lookup_company_context


class TestCompanyContextLookup:
    def test_returns_mock_source_tag(self):
        result = lookup_company_context(company_name="TestCo")
        assert result["source"] == "mock"

    def test_seed_stage_matches_seed_profile(self):
        result = lookup_company_context(company_name="TestCo", stage="Seed")
        assert result["funding_stage"] == "Seed"
        assert result["has_board"] is True
        assert result["has_advisors"] is False

    def test_series_a_stage_matches_series_a_profile(self):
        result = lookup_company_context(company_name="TestCo", stage="Series A")
        assert result["funding_stage"] == "Series A"
        assert result["has_advisors"] is True

    def test_unknown_stage_falls_back_to_default(self):
        result = lookup_company_context(company_name="TestCo", stage="Growth")
        assert result["funding_stage"] == "Pre-seed"  # default profile

    def test_no_stage_falls_back_to_default(self):
        result = lookup_company_context(company_name="TestCo")
        assert result["funding_stage"] == "Pre-seed"

    def test_provided_industry_overrides_mock_sector(self):
        result = lookup_company_context(company_name="TestCo", industry="Biotech", stage="Seed")
        assert result["industry"] == "Biotech"

    def test_description_references_company_name(self):
        result = lookup_company_context(company_name="Unique Company Name")
        assert "Unique Company Name" in result["description"]
