"""Tests for auth endpoints: /api/auth/register, /login, /me."""
import pytest


def test_register_and_login(client):
    resp = client.post("/api/auth/register", json={
        "username": "authuser1",
        "email": "authuser1@test.com",
        "password": "secret123",
        "role": "viewer",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "authuser1"
    assert data["role"] == "viewer"
    assert "id" in data

    # login
    resp = client.post("/api/auth/login", json={
        "username": "authuser1",
        "password": "secret123",
    })
    assert resp.status_code == 200
    token_data = resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "username": "authuser2",
        "email": "authuser2@test.com",
        "password": "rightpass",
        "role": "viewer",
    })
    resp = client.post("/api/auth/login", json={
        "username": "authuser2",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/api/auth/login", json={
        "username": "nobody",
        "password": "anything",
    })
    assert resp.status_code == 401


def test_me_returns_current_user(client, admin_token):
    from tests.conftest import auth
    resp = client.get("/api/auth/me", headers=auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testadmin"
    assert data["role"] == "admin"


def test_me_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_duplicate_username_rejected(client):
    payload = {
        "username": "dupuser",
        "email": "dup@test.com",
        "password": "pass",
        "role": "viewer",
    }
    client.post("/api/auth/register", json=payload)
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400


def test_invalid_role_rejected(client):
    resp = client.post("/api/auth/register", json={
        "username": "roletest",
        "email": "roletest@test.com",
        "password": "pass",
        "role": "superuser",  # not valid
    })
    assert resp.status_code == 400
