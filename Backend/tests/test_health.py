"""Tests for the /health endpoint — no DB or LLM needed."""


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "service" in data
