import asyncio
import time
import pytest
import app.main as _m  # force import (and load_dotenv) at collection time
import app.integrations.telegram as _tg
import app.integrations.discord as _dc
from fastapi.testclient import TestClient


def _client(monkeypatch):
    monkeypatch.setattr(_m, "API_KEY", "testtoken")
    return TestClient(_m.app)


def test_healthz_missing_keys(monkeypatch):
    for key in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    _m._healthz_cache["ts"] = 0.0
    _m._healthz_cache["result"] = None
    monkeypatch.setattr(_m, "detect_ollama", lambda: {"available": False, "models": []})
    client = _client(monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["server"] == "ok"
    non_local = {k: v for k, v in data["providers"].items() if k != "ollama"}
    assert all(v == "missing_key" for v in non_local.values())
    assert data["providers"]["ollama"] == "unavailable"


def test_healthz_with_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    _m._healthz_cache["ts"] = 0.0
    _m._healthz_cache["result"] = None
    monkeypatch.setattr(_m, "detect_ollama", lambda: {"available": True, "models": ["llama3"]})
    client = _client(monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["providers"]["openrouter"] == "ok"
    assert data["providers"]["anthropic"] == "missing_key"
    assert data["providers"]["ollama"] == "ok"


def test_healthz_cache(monkeypatch):
    cached = {"server": "ok", "providers": {"openrouter": "ok"}}
    _m._healthz_cache["ts"] = time.time()
    _m._healthz_cache["result"] = cached
    client = _client(monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == cached


def test_get_mcp_not_ready_returns_initializing(monkeypatch):
    from app.mcp_manager import mcp_manager
    monkeypatch.setattr(mcp_manager, "_is_ready", False)
    client = _client(monkeypatch)
    resp = client.get("/api/mcp")
    assert resp.status_code == 200
    data = resp.json()
    assert data["servers"] == []
    assert data["initializing"] is True


def test_get_mcp_ready_no_reinit(monkeypatch):
    from app.mcp_manager import mcp_manager
    monkeypatch.setattr(mcp_manager, "_is_ready", True)
    monkeypatch.setattr(mcp_manager, "servers", {})
    reinit_called = []
    monkeypatch.setattr(mcp_manager, "initialize_default_servers", lambda *a, **kw: reinit_called.append(1))
    client = _client(monkeypatch)
    resp = client.get("/api/mcp")
    assert resp.status_code == 200
    assert resp.json() == {"servers": []}
    assert reinit_called == []


@pytest.mark.asyncio
async def test_mcp_init_awaited_before_lifespan_yields(monkeypatch):
    """_lifespan must await MCP init so _is_ready is True before the first request."""
    from app.mcp_manager import mcp_manager

    ready_on_entry = []

    async def mock_init(*a, **kw):
        mcp_manager._is_ready = True

    async def noop(*a, **kw):
        pass

    monkeypatch.setattr(mcp_manager, "_is_ready", False)
    monkeypatch.setattr(mcp_manager, "initialize_default_servers", mock_init)
    monkeypatch.setattr(_tg, "start_telegram", noop)
    monkeypatch.setattr(_dc, "start_discord", noop)

    async with _m._lifespan(_m.app):
        ready_on_entry.append(mcp_manager._is_ready)

    assert ready_on_entry[0] is True, "MCP init must complete before lifespan yields"


def test_load_or_create_api_key_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_API_KEY", "mykey123")
    assert _m._load_or_create_api_key() == "mykey123"


def test_load_or_create_api_key_from_file(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    key_dir = tmp_path / "ai_computer"
    key_dir.mkdir()
    (key_dir / ".api_key").write_text("filekey456")
    assert _m._load_or_create_api_key() == "filekey456"


def test_load_or_create_api_key_generates_and_saves(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    key = _m._load_or_create_api_key()
    assert len(key) == 64  # token_hex(32) produces 64 hex chars
    key_file = tmp_path / "ai_computer" / ".api_key"
    assert key_file.exists()
    assert key_file.read_text().strip() == key


@pytest.mark.asyncio
async def test_lifespan_stores_and_cancels_integration_tasks(monkeypatch):
    from app.mcp_manager import mcp_manager

    async def mock_init(*a, **kw):
        pass

    async def long_running(*a, **kw):
        await asyncio.sleep(9999)

    monkeypatch.setattr(mcp_manager, "initialize_default_servers", mock_init)
    monkeypatch.setattr(_tg, "start_telegram", long_running)
    monkeypatch.setattr(_dc, "start_discord", long_running)

    async with _m._lifespan(_m.app):
        assert _m._telegram_task is not None and not _m._telegram_task.done()
        assert _m._discord_task is not None and not _m._discord_task.done()

    assert _m._telegram_task.done()
    assert _m._discord_task.done()


def test_stream_invalid_keepalive_too_low(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get("/api/tasks/sometask/stream?keepalive_timeout_seconds=2", headers={"Authorization": "Bearer testtoken"})
    assert resp.status_code == 400


def test_stream_invalid_keepalive_too_high(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get("/api/tasks/sometask/stream?keepalive_timeout_seconds=400", headers={"Authorization": "Bearer testtoken"})
    assert resp.status_code == 400


def test_active_tasks_empty_when_no_tasks(monkeypatch):
    monkeypatch.setattr(_m, "_tasks", {})
    client = _client(monkeypatch)
    resp = client.get("/api/active-tasks", headers={"Authorization": "Bearer testtoken"})
    assert resp.status_code == 200
    assert resp.json() == {"tasks": []}


@pytest.mark.asyncio
async def test_mcp_watchdog_marks_dead_when_pending_calls_get_no_response():
    """Watchdog transitions status to 'dead' within the timeout when calls are in-flight but silent."""
    from app.mcp_manager import MCPServer

    server = MCPServer("test", ["echo"])
    server.status = "running"
    server._last_response_at = 0.0  # epoch — always expired relative to _WATCHDOG_TIMEOUT

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    server._pending[1] = fut

    task = asyncio.create_task(server._watchdog(poll=0.01))
    await asyncio.sleep(0.05)  # let watchdog tick at least once

    assert server.status == "dead"
    assert fut.done()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def test_active_tasks_returns_non_terminal_only(monkeypatch):
    from app.models import AgentContext, TaskRecord
    running = TaskRecord(id="t1", status="running", context=AgentContext(goal="do stuff"), goal="do stuff", mode="coding", model="gpt-4")
    done = TaskRecord(id="t2", status="done", context=AgentContext(goal="finished"), goal="finished", mode="coding", model="gpt-4")
    monkeypatch.setattr(_m, "_tasks", {"t1": running, "t2": done})
    client = _client(monkeypatch)
    resp = client.get("/api/active-tasks", headers={"Authorization": "Bearer testtoken"})
    assert resp.status_code == 200
    data = resp.json()
    ids = [t["task_id"] for t in data["tasks"]]
    assert "t1" in ids
    assert "t2" not in ids


def test_create_task_queues_when_active_limit_reached(monkeypatch):
    from app.models import AgentContext, TaskRecord

    monkeypatch.setattr(_m, "_tasks", {})
    monkeypatch.setattr(_m, "_queued_task_specs", [])
    monkeypatch.setattr(_m, "_MAX_ACTIVE_TASKS", 0)
    monkeypatch.setattr(_m, "detect_ollama", lambda: {"available": False, "models": []})
    client = _client(monkeypatch)

    resp = client.post(
        "/api/tasks",
        headers={"Authorization": "Bearer testtoken"},
        json={
            "task_id": "queued-task",
            "goal": "do later",
            "model": "claude-3-5-sonnet-20241022",
            "plan_first": True,
            "notify_on_completion": True,
            "auto_commit": True,
            "autonomy_level": "careful",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert _m._tasks["queued-task"].status == "queued"
    assert _m._tasks["queued-task"].plan_first is True
    assert _m._queued_task_specs[0]["autonomy_level"] == "careful"

    cancel = client.delete("/api/tasks/queued-task", headers={"Authorization": "Bearer testtoken"})
    assert cancel.status_code == 200
    assert _m._tasks["queued-task"].status == "cancelled"


def test_task_feedback_endpoint_persists_feedback(monkeypatch, tmp_path):
    from app.models import AgentContext, TaskRecord

    rec = TaskRecord(id="fb-task", status="done", context=AgentContext(goal="finished"), goal="finished")
    monkeypatch.setattr(_m, "_tasks", {"fb-task": rec})
    monkeypatch.setattr(_m, "workspace_dir", tmp_path)
    monkeypatch.setattr(_m, "task_store_dir", tmp_path / "tasks")
    (tmp_path / "tasks").mkdir()
    client = _client(monkeypatch)

    resp = client.post(
        "/api/tasks/fb-task/feedback",
        headers={"Authorization": "Bearer testtoken"},
        json={"rating": "up", "note": "useful"},
    )

    assert resp.status_code == 200
    assert rec.metadata["feedback"][0]["rating"] == "up"
