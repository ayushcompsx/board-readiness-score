"""
Data contracts for the Board Readiness Score pipeline.

Every agent takes one of these as input and returns another as output.
Nothing passes between components as a raw/untyped dict — see Section 5
of the engineering brief: "Do not pass arbitrary dictionaries between
components when a strongly typed schema is appropriate."
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. What the founder submits
# ---------------------------------------------------------------------------

class FounderInput(BaseModel):
    company_name: str
    website: Optional[str] = None
    stage: str  # e.g. "Pre-seed", "Seed", "Series A"
    industry: str
    team_size: int
    founder_background: Optional[str] = None
    current_team_structure: Optional[str] = None
    revenue_or_funding_info: Optional[str] = None
    existing_board_or_advisors: Optional[str] = None
    current_strategic_challenges: Optional[str] = None
    governance_maturity_notes: Optional[str] = None
    areas_seeking_expertise: Optional[str] = None


# ---------------------------------------------------------------------------
# 2. What the MCP enrichment tool returns
# ---------------------------------------------------------------------------

class CompanyContext(BaseModel):
    """
    Output of the MCP `get_company_context` tool.
    This is MOCK data standing in for a future real provider
    (Crunchbase / LinkedIn / Companies House). Every instance is
    explicitly tagged so nothing pretends to be real.
    """
    source: Literal["mock"] = "mock"
    description: Optional[str] = None
    estimated_stage: Optional[str] = None
    industry: Optional[str] = None
    employee_range: Optional[str] = None
    funding_stage: Optional[str] = None
    last_funding_round_usd: Optional[int] = None
    has_board: Optional[bool] = None
    has_advisors: Optional[bool] = None
    governance_signals: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. Enrichment Agent output — founder input + MCP context, merged
# ---------------------------------------------------------------------------

class FieldProvenance(str, Enum):
    """Every fact we use is tagged so we never present a guess as a fact."""
    KNOWN = "known"       # founder told us directly
    INFERRED = "inferred"  # mock enrichment suggested it
    UNKNOWN = "unknown"    # we don't have this


class CompanyProfile(BaseModel):
    founder_input: FounderInput
    company_context: CompanyContext
    # Maps a field name -> how confident/sourced that field is.
    field_provenance: dict[str, FieldProvenance] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 4. Analysis Agent output
# ---------------------------------------------------------------------------

class DimensionName(str, Enum):
    LEADERSHIP_DEPTH = "Leadership depth"
    STRATEGIC_EXPERTISE = "Strategic expertise"
    GOVERNANCE_MATURITY = "Governance maturity"
    FINANCIAL_OVERSIGHT = "Financial oversight"
    COMMERCIAL_EXPERTISE = "Commercial expertise"
    NETWORK_MARKET_ACCESS = "Network / market access"
    OPERATIONAL_MATURITY = "Operational maturity"
    BOARD_ADVISOR_STRUCTURE = "Board/advisor structure"


class DimensionScore(BaseModel):
    name: DimensionName
    score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class CapabilityGap(BaseModel):
    dimension: DimensionName
    severity: Literal["low", "medium", "high"]
    evidence: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    suggested_advisor_profile: str


class BoardAnalysis(BaseModel):
    dimension_scores: list[DimensionScore]
    gaps: list[CapabilityGap]
    strengths: list[str] = Field(default_factory=list)
    overall_score: int = Field(ge=0, le=100)  # calculated deterministically, not by the LLM


# ---------------------------------------------------------------------------
# 5. Report Agent output — the final thing the founder sees
# ---------------------------------------------------------------------------

class ReportGapSection(BaseModel):
    title: str
    why_it_matters: str
    evidence: list[str]
    suggested_advisor_profile: str


class BoardReadinessReport(BaseModel):
    overall_score: int
    executive_summary: str
    strengths: list[str]
    gap_sections: list[ReportGapSection]
    governance_current_signals: list[str]
    governance_improvements: list[str]
    recommended_next_steps: list[str]
    cta_text: str = "Get matched with Connectd advisors"


# ---------------------------------------------------------------------------
# 6. Lead scoring — separate concept from the board readiness score
# ---------------------------------------------------------------------------

class LeadTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    LOW = "low"


class LeadScore(BaseModel):
    score: int = Field(ge=0, le=100)
    tier: LeadTier
    signals: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 7. Run metadata / observability
# ---------------------------------------------------------------------------

class AgentRunMetadata(BaseModel):
    agent_name: str
    started_at: datetime
    duration_ms: float
    success: bool
    validation_errors: list[str] = Field(default_factory=list)
    retry_count: int = 0


class AssessmentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class AssessmentRun(BaseModel):
    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    status: AssessmentStatus = AssessmentStatus.PENDING
    founder_input: FounderInput
    company_profile: Optional[CompanyProfile] = None
    board_analysis: Optional[BoardAnalysis] = None
    report: Optional[BoardReadinessReport] = None
    lead_score: Optional[LeadScore] = None
    run_metadata: list[AgentRunMetadata] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
