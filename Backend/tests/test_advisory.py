"""
Tests for /ask, /history, /feedback, and /feedback/summary endpoints.
DB and LLM calls are mocked — no real MySQL, Ollama, or Groq needed.
"""
import io
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from main import create_token, hash_password


def _auth_header(user_id=1, username="testfarmer"):
    return {"Authorization": f"Bearer {create_token(user_id, username)}"}


# ── /ask — text query ─────────────────────────────────────────────────────────

def test_ask_text_query_success(client, fake_db):
    conn, cursor = fake_db
    mock_ollama = MagicMock()
    mock_ollama.chat.return_value = MagicMock(
        message=MagicMock(content="Use drip irrigation and apply urea carefully.")
    )
    with patch("main.get_db", return_value=conn), \
         patch("main.OLLAMA_CLIENT", mock_ollama), \
         patch("main._groq_client", None):
        resp = client.post("/ask", data={"query": "How to improve wheat yield?", "language": "en"})
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert isinstance(data["policies"], list)
    assert data["detected"] is None


def test_ask_returns_weather_key(client, fake_db):
    conn, _ = fake_db
    mock_ollama = MagicMock()
    mock_ollama.chat.return_value = MagicMock(message=MagicMock(content="Advisory text."))
    with patch("main.get_db", return_value=conn), \
         patch("main.OLLAMA_CLIENT", mock_ollama), \
         patch("main._groq_client", None):
        resp = client.post("/ask", data={"query": "soil health tips"})
    assert "weather" in resp.json()


def test_ask_rate_limit(client, fake_db):
    conn, _ = fake_db
    mock_ollama = MagicMock()
    mock_ollama.chat.return_value = MagicMock(message=MagicMock(content="ok"))
    # Exhaust the in-memory rate limit (15 req/min) for a fake IP
    with patch("main._check_rate_limit", return_value=False):
        resp = client.post("/ask", data={"query": "test"})
    assert resp.status_code == 429


def test_ask_unsupported_image_type(client):
    fake_pdf = io.BytesIO(b"%PDF fake content")
    resp = client.post(
        "/ask",
        data={"query": "what is this?"},
        files={"file": ("doc.pdf", fake_pdf, "application/pdf")},
    )
    assert resp.status_code == 400


def test_ask_image_diagnosis(client, fake_db):
    """Upload a synthetic leaf image and verify diagnosis fields are present."""
    from PIL import Image as PILImage

    # Build a 224×224 green leaf-ish image
    img = PILImage.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    conn, cursor = fake_db
    # Mock model to return a prediction array favouring class index 31 (Tomato_healthy)
    fake_preds = np.zeros(39, dtype="float32")
    fake_preds[31] = 0.95
    fake_preds[30] = 0.03
    fake_preds[32] = 0.02

    mock_ollama = MagicMock()
    mock_ollama.chat.return_value = MagicMock(message=MagicMock(content="Plant looks healthy."))

    with patch("main.get_db", return_value=conn), \
         patch("main.OLLAMA_CLIENT", mock_ollama), \
         patch("main._groq_client", None), \
         patch("main.MODEL") as mock_model:
        mock_model.predict.return_value = np.array([fake_preds])
        resp = client.post(
            "/ask",
            data={"query": "What disease does this leaf have?"},
            files={"file": ("leaf.jpg", buf, "image/jpeg")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["detected"] == "Tomato_healthy"
    assert data["confidence"] == pytest.approx(0.95, abs=0.01)
    assert isinstance(data["top3"], list)
    assert len(data["top3"]) == 3


# ── /history ──────────────────────────────────────────────────────────────────

def test_history_requires_auth(client):
    resp = client.get("/history")
    assert resp.status_code == 401


def test_history_with_valid_token(client, fake_db):
    conn, cursor = fake_db
    cursor.fetchall.return_value = [
        {"user_query": "wheat yield?", "ai_response": "Use balanced NPK.", "created_at": "2025-01-01"}
    ]
    with patch("main.get_db", return_value=conn):
        resp = client.get("/history", headers=_auth_header(user_id=1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["history"][0]["user_query"] == "wheat yield?"


def test_history_expired_token(client):
    # Craft a token with 0-hour expiry to simulate expiry
    import jwt, os
    from datetime import datetime, timezone
    payload = {"sub": "x", "user_id": 1, "exp": datetime(2000, 1, 1, tzinfo=timezone.utc)}
    expired_token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    resp = client.get("/history", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


# ── /feedback ─────────────────────────────────────────────────────────────────

def test_feedback_submit_success(client, fake_db):
    conn, _ = fake_db
    with patch("main.get_db", return_value=conn):
        resp = client.post("/feedback", json={
            "name": "Gurpreet Singh",
            "mobile": "9876543210",
            "category": "crop",
            "rating": 5,
            "feedback": "Very helpful advisory system!",
        })
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_feedback_invalid_rating(client):
    resp = client.post("/feedback", json={
        "name": "Test",
        "mobile": "1234567890",
        "category": "general",
        "rating": 6,
        "feedback": "Bad rating value",
    })
    assert resp.status_code == 400


# ── /feedback/summary ─────────────────────────────────────────────────────────

def test_feedback_summary(client, fake_db):
    conn, cursor = fake_db
    # Three separate cursor.execute calls — return different data each time
    cursor.fetchone.return_value = {"total": 10, "avg_rating": 4.2}
    cursor.fetchall.side_effect = [
        [{"rating": 4, "count": 6}, {"rating": 5, "count": 4}],
        [{"category": "crop", "count": 7, "avg_rating": 4.3}],
    ]
    with patch("main.get_db", return_value=conn):
        resp = client.get("/feedback/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["average_rating"] == pytest.approx(4.2, abs=0.01)
    assert isinstance(data["distribution"], list)
    assert isinstance(data["by_category"], list)
