"""
Shared pytest fixtures.
The test client is session-scoped so main.py is imported once.
DB and LLM calls are mocked per-test — no real MySQL or network needed.
"""
import os

# Set env vars before main.py is imported so constants pick them up
os.environ.setdefault("JWT_SECRET", "pytest-secret-do-not-use-in-prod")
os.environ.setdefault("DB_PASSWORD", "")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("REDIS_URL", "")

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """One TestClient for the whole test session (avoids repeated TF loads)."""
    from main import app
    return TestClient(app)


@pytest.fixture
def fake_db():
    """
    Returns (conn_mock, cursor_mock).
    cursor.fetchone() returns None by default — override per test.
    """
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor
