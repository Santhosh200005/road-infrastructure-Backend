"""
Tests for POST /api/simulate and POST /api/simulate/series.

XGBoost model calls are patched so tests run without xgb_simulator.json.
"""
import pytest
from unittest.mock import patch
from tests.conftest import auth

# Raw output that ml/simulator/simulate.py::forecast_severity() returns
MOCK_FORECAST_RESULT = {
    "current_severity": 3.0,
    "forecast_days": 30,
    "predicted_severity": 3.7265,
}

BASE_INPUTS = {
    "current_severity": 3.0,
    "daily_vehicles": 8000,
    "rainfall_mm": 20.0,
    "avg_temp": 15.0,
    "road_age_years": 10.0,
    "last_repair_days": 500,
    "material_type": 1,
}


@pytest.fixture
def mock_simulator():
    """Patch the XGBoost runner so no model file is needed."""
    with patch(
        "backend.ml_bridge.simulator_runner.run_simulation",
        return_value=dict(MOCK_FORECAST_RESULT),
    ) as m:
        yield m


def test_simulate_single_point(client, admin_token, mock_simulator):
    payload = {**BASE_INPUTS, "forecast_days": 30}
    resp = client.post("/api/simulate", json=payload, headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_severity" in data
    assert "condition" in data
    assert "remaining_life_years" in data
    assert "failure_probability" in data
    assert "simulation_id" in data
    assert data["forecast_days"] == 30


def test_simulate_accepts_days_alias(client, admin_token):
    """Frontend sends 'days' (not 'forecast_days') — both must work."""
    def _mock_run_simulation(inputs, days=30):
        return {
            "current_severity": inputs.get("current_severity", 3.0),
            "forecast_days": days,
            "predicted_severity": inputs.get("current_severity", 3.0) + 0.5,
        }

    with patch(
        "backend.ml_bridge.simulator_runner.run_simulation",
        side_effect=_mock_run_simulation,
    ):
        payload = {**BASE_INPUTS, "days": 60}
        resp = client.post("/api/simulate", json=payload, headers=auth(admin_token))

    assert resp.status_code == 200
    data = resp.json()
    # The route uses payload.forecast_days which was normalised from 'days'
    assert data["forecast_days"] == 60


def test_simulate_condition_labels(client, admin_token):
    """Verify condition labels are computed correctly from severity thresholds."""
    cases = [
        ({"predicted_severity": 2.0, "forecast_days": 30, "current_severity": 2.0}, "Good"),
        ({"predicted_severity": 4.0, "forecast_days": 30, "current_severity": 3.0}, "Fair"),
        ({"predicted_severity": 6.0, "forecast_days": 30, "current_severity": 5.0}, "Poor"),
        ({"predicted_severity": 8.0, "forecast_days": 30, "current_severity": 6.0}, "Critical"),
    ]
    for mock_result, expected_condition in cases:
        with patch(
            "backend.ml_bridge.simulator_runner.run_simulation",
            return_value=mock_result,
        ):
            resp = client.post(
                "/api/simulate",
                json={**BASE_INPUTS, "forecast_days": 30},
                headers=auth(admin_token),
            )
            assert resp.status_code == 200
            assert resp.json()["condition"] == expected_condition


def test_simulate_requires_auth(client):
    resp = client.post("/api/simulate", json={**BASE_INPUTS, "forecast_days": 30})
    assert resp.status_code == 401


def test_simulate_series(client, admin_token):
    """Series endpoint returns multiple points for the frontend LineChart."""
    # Mock returns the same value for each day-point (sufficient for structure test)
    with patch(
        "backend.ml_bridge.simulator_runner.run_simulation_series",
        return_value=[
            {"current_severity": 3.0, "forecast_days": d, "predicted_severity": 3.0 + d * 0.01}
            for d in [0, 10, 20, 30, 45, 60, 90, 120, 150, 180]
        ],
    ):
        resp = client.post(
            "/api/simulate/series",
            json=BASE_INPUTS,
            headers=auth(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "points" in data
    assert len(data["points"]) == 10
    days = [p["forecast_days"] for p in data["points"]]
    assert 0 in days and 180 in days
