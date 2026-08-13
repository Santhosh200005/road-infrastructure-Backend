"""
Tests for POST /api/agents/run and GET /api/agents/reports.

The CrewAI crew itself (backend.agents.crew.run_crew) is fully mocked so
these tests never make a real OpenAI API call and never require crewai
to be installed at test time.
"""
import pytest
from unittest.mock import patch
from tests.conftest import auth

MOCK_CREW_RESULT = {
    "reasoning": (
        "Prioritized 2 defects: 1 Critical pothole on a high-traffic road, "
        "1 Medium crack. Allocated ₹500 of the ₹500,000 budget. "
        "Scheduled Crew 1 for Day 1 pothole patch."
    ),
    "raw_output": "Full crew output text...",
    "priority_breakdown": {"Critical": 1, "High": 0, "Medium": 1, "Low": 0},
    "total_estimated_cost": 500.0,
}


@pytest.fixture
def mock_crew():
    with patch(
        "backend.agents.crew.run_crew",
        return_value=dict(MOCK_CREW_RESULT),
    ) as m:
        yield m


def test_run_agents_as_engineer(client, engineer_token, mock_crew):
    resp = client.post(
        "/api/agents/run",
        json={"budget": 500000, "num_crews": 3},
        headers=auth(engineer_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "date" in data
    assert data["priority_breakdown"] == {"Critical": 1, "High": 0, "Medium": 1, "Low": 0}
    assert data["total_estimated_cost"] == 500.0
    assert "reasoning" in data


def test_run_agents_forbidden_for_viewer(client, viewer_token, mock_crew):
    resp = client.post(
        "/api/agents/run",
        json={"budget": 500000, "num_crews": 3},
        headers=auth(viewer_token),
    )
    assert resp.status_code == 403


def test_run_agents_requires_auth(client, mock_crew):
    resp = client.post("/api/agents/run", json={"budget": 500000, "num_crews": 3})
    assert resp.status_code == 401


def test_run_agents_missing_api_key_returns_503(client, engineer_token):
    """If OPENAI_API_KEY isn't set / crewai isn't installed, expect 503, not 500."""
    with patch(
        "backend.agents.crew.run_crew",
        side_effect=RuntimeError("OPENAI_API_KEY environment variable is not set."),
    ):
        resp = client.post(
            "/api/agents/run",
            json={"budget": 500000, "num_crews": 3},
            headers=auth(engineer_token),
        )
    assert resp.status_code == 503


def test_agent_reports_lists_past_runs(client, admin_token, engineer_token, mock_crew):
    client.post(
        "/api/agents/run",
        json={"budget": 500000, "num_crews": 3},
        headers=auth(engineer_token),
    )
    resp = client.get("/api/agents/reports", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Verify shape matches frontend AgentReports.jsx expectations exactly
    report = data[0]
    for key in ["id", "date", "defects_processed", "priority_breakdown",
                "total_estimated_cost", "reasoning"]:
        assert key in report


def test_agent_reports_requires_auth(client):
    resp = client.get("/api/agents/reports")
    assert resp.status_code == 401


def test_run_agents_default_budget_and_crews(client, engineer_token, mock_crew):
    """Empty body should still work — defaults kick in."""
    resp = client.post(
        "/api/agents/run",
        json={},
        headers=auth(engineer_token),
    )
    assert resp.status_code == 201
