"""
Mock company enrichment lookup.

This simulates what a real provider (Crunchbase, LinkedIn, Companies
House) would return for `get_company_context`. It is NOT real data —
every result is explicitly tagged source="mock" (see CompanyContext
schema). Swapping this file for a real API call later is the intended
upgrade path; nothing outside this file should need to change to do so.
"""
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "companies.json"


def _load_mock_data() -> dict:
    with open(DATA_PATH) as f:
        return json.load(f)


def lookup_company_context(
    company_name: str,
    website: str | None = None,
    industry: str | None = None,
    stage: str | None = None,
) -> dict:
    """
    Picks the closest mock profile based on the founder-reported stage.
    This is a simple heuristic, not real lookup — a real integration
    would query an external API by company_name/website instead.
    """
    data = _load_mock_data()

    stage_key_map = {
        "pre-seed": "default",
        "seed": "seed_example",
        "series a": "series_a_example",
    }

    key = "default"
    if stage:
        key = stage_key_map.get(stage.strip().lower(), "default")

    profile = data.get(key, data["default"])

    return {
        "source": "mock",
        "description": f"Mock enrichment for {company_name} "
        f"(matched against '{key}' reference profile).",
        "estimated_stage": profile.get("funding_stage"),
        "industry": industry or profile.get("sector"),
        "employee_range": f"~{profile.get('team_size')}",
        "funding_stage": profile.get("funding_stage"),
        "last_funding_round_usd": profile.get("last_funding_round_usd"),
        "has_board": profile.get("has_board"),
        "has_advisors": profile.get("has_advisors"),
        "governance_signals": profile.get("notes"),
    }
