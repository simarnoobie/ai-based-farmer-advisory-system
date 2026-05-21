"""
Tests for /signup and /login endpoints.
DB calls are mocked — no real MySQL needed.
"""
import pytest
from unittest.mock import patch
from main import hash_password, verify_password, create_token, decode_token


# ── Unit tests for password helpers ───────────────────────────────────────────

def test_hash_password_is_not_plaintext():
    h = hash_password("mysecret")
    assert h != "mysecret"
    assert len(h) > 20


def test_verify_password_correct():
    h = hash_password("mysecret")
    assert verify_password("mysecret", h) is True


def test_verify_password_wrong():
    h = hash_password("mysecret")
    assert verify_password("wrongpass", h) is False


def test_verify_password_empty_stored():
    assert verify_password("anything", "") is False


# ── Unit tests for JWT helpers ────────────────────────────────────────────────

def test_create_and_decode_token():
    token = create_token(user_id=42, username="farmuser")
    payload = decode_token(token)
    assert payload["user_id"] == 42
    assert payload["sub"] == "farmuser"


# ── Integration tests for /signup ─────────────────────────────────────────────

def test_signup_success(client, fake_db):
    conn, cursor = fake_db
    cursor.fetchone.return_value = None  # username not taken
    with patch("main.get_db", return_value=conn):
        resp = client.post("/signup", json={"username": "newfarmer", "password": "pass1234"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_signup_duplicate_username(client, fake_db):
    conn, cursor = fake_db
    cursor.fetchone.return_value = {"id": 1}  # username already exists
    with patch("main.get_db", return_value=conn):
        resp = client.post("/signup", json={"username": "existing", "password": "pass1234"})
    assert resp.status_code == 409


def test_signup_username_too_short(client):
    resp = client.post("/signup", json={"username": "ab", "password": "pass1234"})
    assert resp.status_code == 400


def test_signup_password_too_short(client):
    resp = client.post("/signup", json={"username": "validuser", "password": "abc"})
    assert resp.status_code == 400


# ── Integration tests for /login ──────────────────────────────────────────────

def test_login_success(client, fake_db):
    conn, cursor = fake_db
    hashed = hash_password("correctpass")
    cursor.fetchone.return_value = {"id": 5, "username": "farmer1", "password": hashed}
    with patch("main.get_db", return_value=conn):
        resp = client.post("/login", json={"username": "farmer1", "password": "correctpass"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "token" in data
    assert "user_id" in data


def test_login_wrong_password(client, fake_db):
    conn, cursor = fake_db
    hashed = hash_password("correctpass")
    cursor.fetchone.return_value = {"id": 5, "username": "farmer1", "password": hashed}
    with patch("main.get_db", return_value=conn):
        resp = client.post("/login", json={"username": "farmer1", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_user_not_found(client, fake_db):
    conn, cursor = fake_db
    cursor.fetchone.return_value = None  # user doesn't exist
    with patch("main.get_db", return_value=conn):
        resp = client.post("/login", json={"username": "ghost", "password": "anypass"})
    assert resp.status_code == 401


def test_login_returns_valid_jwt(client, fake_db):
    conn, cursor = fake_db
    hashed = hash_password("mypass123")
    cursor.fetchone.return_value = {"id": 7, "username": "jwtuser", "password": hashed}
    with patch("main.get_db", return_value=conn):
        resp = client.post("/login", json={"username": "jwtuser", "password": "mypass123"})
    token = resp.json()["token"]
    payload = decode_token(token)
    assert payload["user_id"] == 7
    assert payload["sub"] == "jwtuser"
