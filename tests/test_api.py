"""Tests for the API layer (Section 20)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import AssessmentRun, AssessmentStatus, FounderInput

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_check_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAssessmentEndpoints:
    def test_create_assessment_with_invalid_payload_returns_422(self):
        # Missing required fields (company_name, stage, industry, team_size)
        response = client.post("/api/assessment", json={})
        assert response.status_code == 422

    def test_get_unknown_assessment_returns_404(self):
        response = client.get("/api/assessment/does-not-exist")
        assert response.status_code == 404

    def test_create_assessment_calls_pipeline_and_stores_result(self):
        founder_input = FounderInput(
            company_name="TestCo", stage="Seed", industry="Fintech", team_size=10
        )
        fake_run = AssessmentRun(
            founder_input=founder_input, status=AssessmentStatus.COMPLETE
        )

        with patch(
            "app.api.assessment.run_assessment", new=AsyncMock(return_value=fake_run)
        ):
            response = client.post(
                "/api/assessment",
                json={
                    "company_name": "TestCo",
                    "stage": "Seed",
                    "industry": "Fintech",
                    "team_size": 10,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["assessment_id"] == fake_run.assessment_id

        # Confirm it was actually stored and retrievable
        get_response = client.get(f"/api/assessment/{fake_run.assessment_id}")
        assert get_response.status_code == 200
        assert get_response.json()["assessment_id"] == fake_run.assessment_id
