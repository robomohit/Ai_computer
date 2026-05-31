import importlib
import uuid
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient


def _client(monkeypatch, origins="http://localhost:8000"):
    monkeypatch.setenv("AGENT_API_KEY", "token123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", origins)
    import app.main as m

    importlib.reload(m)
    monkeypatch.setattr(m, "API_KEY", "token123")
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


def test_task_id_rejects_path_traversal(monkeypatch):
    client, m = _client(monkeypatch)
    r = client.post(
        "/api/tasks",
        json={"task_id": "../leak", "goal": "test goal"},
        headers={"Authorization": "Bearer token123"},
    )
    assert r.status_code == 422
    assert not (m.task_store_dir.parent / "leak.json").exists()


def test_create_task_internal_error_does_not_leak_details(monkeypatch):
    client, m = _client(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("secret-provider-token")

    monkeypatch.setattr(m.service, "init_task", boom)
    r = client.post(
        "/api/tasks",
        json={"task_id": f"err-{uuid.uuid4().hex}", "goal": "test goal"},
        headers={"Authorization": "Bearer token123"},
    )
    assert r.status_code == 500
    assert r.json()["detail"] == "Internal server error"
    assert "secret-provider-token" not in r.text


def test_cors_reject(monkeypatch):
    client, _ = _client(monkeypatch, origins="http://allowed.local")
    r = client.options(
        "/api/health",
        headers={"Origin": "http://bad.local", "Access-Control-Request-Method": "GET"},
    )
    # Bad origin should NOT be reflected in the allow header
    assert r.headers.get("access-control-allow-origin") != "http://bad.local"


def test_sensitive_utility_routes_require_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_COMPUTER_WORKSPACE", str(tmp_path))
    client, _ = _client(monkeypatch)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me", encoding="utf-8")

    probes = [
        ("POST", "/api/capsule/delete", {"file_paths": [str(victim)]}),
        ("POST", "/api/capsule/restore-delete", {"items": [{"trash_path": "x", "original": "y"}]}),
        ("POST", "/api/connectors/gmail/link", {"notes": "x"}),
        ("POST", "/api/desktop/autostart", {"enabled": False}),
        ("POST", "/api/desktop/trust", {"exe_name": "notepad.exe", "level": "ask"}),
        ("POST", "/api/desktop/send-to", {"target": "clipboard", "text": "secret"}),
    ]

    for method, path, payload in probes:
        response = client.request(method, path, json=payload)
        assert response.status_code == 401, path

    assert victim.exists()


def test_mutating_api_routes_have_auth_or_explicit_public_exception(monkeypatch):
    _, module = _client(monkeypatch)
    public_mutating = {
        "/api/session",
        "/api/capsule/widget",  # local passive widget event bridge
    }
    manual_auth = {
        "/api/capsule/organize",
        "/api/capsule/delete",
        "/api/capsule/restore-delete",
        "/api/capsule/scan",
    }
    missing = []

    for route in module.app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        methods = route.methods - {"HEAD", "OPTIONS"}
        if not methods.intersection({"POST", "PUT", "PATCH", "DELETE"}):
            continue
        if route.path in public_mutating or route.path in manual_auth:
            continue
        deps = [getattr(dep.dependency, "__name__", "") for dep in route.dependencies]
        if "verify_token" not in deps:
            missing.append(f"{','.join(sorted(methods))} {route.path}")

    assert missing == []


def test_capsule_delete_is_reversible_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_COMPUTER_WORKSPACE", str(tmp_path))
    client, _ = _client(monkeypatch)
    victim = tmp_path / "victim.txt"
    victim.write_text("restore me", encoding="utf-8")

    response = client.post(
        "/api/capsule/delete",
        json={"file_paths": [str(victim)]},
        headers={"Authorization": "Bearer token123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["permanent"] is False
    assert body["count"] == 1
    assert not victim.exists()
    trash_path = Path(body["trashed"][0]["trash_path"])
    assert trash_path.exists()

    restore = client.post(
        "/api/capsule/restore-delete",
        json={"items": body["trashed"]},
        headers={"Authorization": "Bearer token123"},
    )

    assert restore.status_code == 200
    assert restore.json()["count"] == 1
    assert victim.read_text(encoding="utf-8") == "restore me"
    assert not trash_path.exists()
