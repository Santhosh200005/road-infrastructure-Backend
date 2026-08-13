"""Tests for /api/roads."""
from tests.conftest import auth


def test_create_road_as_engineer(client, engineer_token):
    resp = client.post(
        "/api/roads",
        json={
            "name": "MG Road",
            "latitude": 17.385,
            "longitude": 78.4867,
            "length_km": 3.2,
            "road_age_years": 15,
            "material_type": 1,
            "daily_vehicles": 12000,
            "last_repair_days": 400,
        },
        headers=auth(engineer_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "MG Road"
    assert "id" in data


def test_create_road_forbidden_for_viewer(client, viewer_token):
    resp = client.post(
        "/api/roads",
        json={"name": "Blocked Road", "latitude": 1.0, "longitude": 1.0},
        headers=auth(viewer_token),
    )
    assert resp.status_code == 403


def test_list_roads(client, admin_token, engineer_token):
    client.post(
        "/api/roads",
        json={"name": "List Test Road", "latitude": 2.0, "longitude": 2.0},
        headers=auth(engineer_token),
    )
    resp = client.get("/api/roads", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_get_road_by_id(client, admin_token, engineer_token):
    create_resp = client.post(
        "/api/roads",
        json={"name": "Fetch Me Road", "latitude": 3.0, "longitude": 3.0},
        headers=auth(engineer_token),
    )
    road_id = create_resp.json()["id"]

    resp = client.get(f"/api/roads/{road_id}", headers=auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fetch Me Road"


def test_get_nonexistent_road_404(client, admin_token):
    resp = client.get("/api/roads/does-not-exist", headers=auth(admin_token))
    assert resp.status_code == 404


def test_roads_require_auth(client):
    resp = client.get("/api/roads")
    assert resp.status_code == 401
