"""Tests for the /health endpoint."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_docs_available(client):
    """Swagger UI should be reachable (proves app starts and routes are wired)."""
    resp = client.get("/docs")
    assert resp.status_code == 200
