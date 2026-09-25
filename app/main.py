"""
FastAPI entrypoint.

Right now this only has a health check — the real /api/assessment
endpoint gets wired up in a later phase, once the agents exist.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assessment import router as assessment_router
from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Board Readiness Score API",
    description="Agentic lead magnet for Connectd — assesses a startup's "
    "board/advisory readiness and generates a personalised report.",
    version="0.1.0",
)

# Allow the local frontend (served separately) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for local demo; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessment_router)


@app.get("/api/health")
def health_check():
    """
    Basic liveness check. In a later phase this should also verify
    Ollama and the MCP server are reachable, not just that FastAPI itself
    is up.
    """
    logger.info("Health check called")
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "model_provider": settings.model_provider,
    }
