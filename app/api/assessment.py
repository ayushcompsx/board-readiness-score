"""
Assessment API routes.

POST /api/assessment  — submit founder input, runs the full pipeline,
                         returns the complete AssessmentRun (even on
                         failure — status field tells you what happened).
GET  /api/assessment/{id} — retrieve a previously run assessment.

Storage: in-memory dict for this demo. This is explicitly NOT
production-appropriate (state is lost on restart, not shared across
processes) — see README "Production Evolution" for the Postgres-backed
version. Flagging this clearly rather than pretending it's durable.
"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import AssessmentRun, FounderInput
from app.orchestration.pipeline import run_assessment
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["assessment"])

# In-memory store — demo only, see docstring above.
_assessment_store: dict[str, AssessmentRun] = {}


@router.post("/assessment", response_model=AssessmentRun)
async def create_assessment(founder_input: FounderInput) -> AssessmentRun:
    run = await run_assessment(founder_input)
    _assessment_store[run.assessment_id] = run
    return run


@router.get("/assessment/{assessment_id}", response_model=AssessmentRun)
async def get_assessment(assessment_id: str) -> AssessmentRun:
    run = _assessment_store.get(assessment_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return run
