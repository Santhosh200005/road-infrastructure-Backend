"""Tests for /api/repairs (GET, POST, PATCH)."""
from tests.conftest import auth


def test_create_repair_as_engineer(client, engineer_token):
    resp = client.post(
        "/api/repairs",
        json={
            "defect_class": "D40",
            "priority": "High",
        },
        headers=auth(engineer_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["defect_class"] == "D40"
    assert data["status"] == "pending"
    assert "id" in data


def test_create_repair_forbidden_for_viewer(client, viewer_token):
    resp = client.post(
        "/api/repairs",
        json={"defect_class": "D00", "priority": "Low"},
        headers=auth(viewer_token),
    )
    assert resp.status_code == 403


def test_list_repairs(client, admin_token, engineer_token):
    client.post(
        "/api/repairs",
        json={"defect_class": "D20", "priority": "Critical"},
        headers=auth(engineer_token),
    )
    resp = client.get("/api/repairs", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_list_repairs_filtered_by_status(client, admin_token):
    resp = client.get("/api/repairs?status=pending", headers=auth(admin_token))
    assert resp.status_code == 200
    for r in resp.json():
        assert r["status"] == "pending"


def test_update_repair_status(client, engineer_token):
    create_resp = client.post(
        "/api/repairs",
        json={"defect_class": "D10", "priority": "Medium"},
        headers=auth(engineer_token),
    )
    repair_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/repairs/{repair_id}",
        json={"status": "in_progress", "assigned_crew": "Crew A"},
        headers=auth(engineer_token),
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["status"] == "in_progress"
    assert data["assigned_crew"] == "Crew A"


def test_update_repair_to_completed_sets_completed_date(client, engineer_token):
    create_resp = client.post(
        "/api/repairs",
        json={"defect_class": "D40", "priority": "High"},
        headers=auth(engineer_token),
    )
    repair_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/repairs/{repair_id}",
        json={"status": "completed"},
        headers=auth(engineer_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["completed_date"] is not None


def test_update_nonexistent_repair_404(client, engineer_token):
    resp = client.patch(
        "/api/repairs/does-not-exist",
        json={"status": "completed"},
        headers=auth(engineer_token),
    )
    assert resp.status_code == 404


def test_repairs_require_auth(client):
    resp = client.get("/api/repairs")
    assert resp.status_code == 401
