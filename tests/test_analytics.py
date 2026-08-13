"""Tests for /api/analytics, /api/analytics/map, /api/analytics/budget, /api/dashboard."""
from tests.conftest import auth


def test_analytics_requires_auth(client):
    resp = client.get("/api/analytics")
    assert resp.status_code == 401


def test_analytics_returns_full_shape(client, admin_token):
    resp = client.get("/api/analytics", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "damage_statistics" in data
    assert "monthly_reports" in data
    assert "heatmap" in data
    assert "road_health_trend" in data
    assert "prediction_history" in data
    assert "by_class" in data["damage_statistics"]
    assert "by_severity" in data["damage_statistics"]


def test_analytics_map_returns_list(client, admin_token):
    resp = client.get("/api/analytics/map", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_analytics_budget_matches_frontend_shape(client, admin_token):
    """
    Must match Analytics.jsx's expected shape exactly:
    { monthly: [...], byType: [...], cumulative: [...] }
    """
    resp = client.get("/api/analytics/budget", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "monthly" in data
    assert "byType" in data
    assert "cumulative" in data
    assert isinstance(data["monthly"], list)
    assert isinstance(data["byType"], list)
    assert isinstance(data["cumulative"], list)


def test_dashboard_summary(client, admin_token):
    resp = client.get("/api/dashboard", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    for key in [
        "total_roads", "total_potholes", "total_detections",
        "high_risk_roads", "pending_repairs", "completed_repairs",
        "average_confidence", "average_remaining_life",
    ]:
        assert key in data


def test_dashboard_requires_auth(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 401
