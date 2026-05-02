import time
import pytest
import app.main as _m  # force import (and load_dotenv) at collection time
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
