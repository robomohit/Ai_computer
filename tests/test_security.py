import importlib
import uuid

from fastapi.testclient import TestClient


def _client(monkeypatch, origins="http://localhost:8000"):
    monkeypatch.setenv("AGENT_API_KEY", "token123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", origins)
    import app.main as m

    importlib.reload(m)
    return TestClient(m.app), m


def test_config_does_not_expose_permanent_api_key(monkeypatch):
    client, m = _client(monkeypatch)
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert "api_key" not in body
    assert "token123" not in r.text

    r2 = client.post("/api/tasks", json={"task_id": "1", "goal": "test goal"})
    assert r2.status_code == 401


def test_permanent_api_key_still_authenticates_server_api(monkeypatch):
    client, m = _client(monkeypatch)
    task_id = f"auth-{uuid.uuid4().hex}"
    r = client.post("/api/tasks", json={"task_id": task_id, "goal": "test goal"}, headers={"Authorization": "Bearer token123"})
    assert r.status_code == 200


def test_session_bootstrap_authenticates_without_revealing_api_key(monkeypatch):
    client, m = _client(monkeypatch)
    session = client.post("/api/session")
    assert session.status_code == 200
    assert "token123" not in session.text

    task_id = f"session-{uuid.uuid4().hex}"
    r = client.post("/api/tasks", json={"task_id": task_id, "goal": "test goal"})
    assert r.status_code == 200


def test_query_token_is_not_accepted_for_sse(monkeypatch):
    client, m = _client(monkeypatch)
    r = client.get("/api/tasks/nope/stream?token=token123")
    assert r.status_code == 401


def test_cors_reject(monkeypatch):
    client, _ = _client(monkeypatch, origins="http://allowed.local")
    r = client.options(
        "/api/health",
        headers={"Origin": "http://bad.local", "Access-Control-Request-Method": "GET"},
    )
    # Bad origin should NOT be reflected in the allow header
    assert r.headers.get("access-control-allow-origin") != "http://bad.local"
