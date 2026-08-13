"""
Shared pytest fixtures.

Uses an in-memory SQLite database so tests run without a live Postgres
instance. All tables are created fresh per test session.

Heavy operations (YOLO inference, CrewAI LLM calls) are monkey-patched out
so tests are fast and free of API keys / GPU requirements.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Point at in-memory SQLite before importing the app
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_road_infra.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

from backend.database.db import Base, get_db  # noqa: E402
from backend.main import app                  # noqa: E402

TEST_DB_URL = "sqlite:///./test_road_infra.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the entire test session."""
    from backend.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client():
    """TestClient for the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """Per-test DB session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _register_and_login(client: TestClient, username: str, role: str = "admin") -> str:
    """Register a user and return a valid JWT token."""
    client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "testpass123",
        "role": role,
    })
    resp = client.post("/api/auth/login", json={
        "username": username,
        "password": "testpass123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(client):
    return _register_and_login(client, "testadmin", "admin")


@pytest.fixture(scope="session")
def engineer_token(client):
    return _register_and_login(client, "testengineer", "engineer")


@pytest.fixture(scope="session")
def viewer_token(client):
    return _register_and_login(client, "testviewer", "viewer")


def auth(token: str) -> dict:
    """Return Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}
