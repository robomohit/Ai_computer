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
    client = _client(monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["server"] == "ok"
    assert all(v == "missing_key" for v in data["providers"].values())


def test_healthz_with_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    _m._healthz_cache["ts"] = 0.0
    _m._healthz_cache["result"] = None
    client = _client(monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["providers"]["openrouter"] == "ok"
    assert data["providers"]["anthropic"] == "missing_key"


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
