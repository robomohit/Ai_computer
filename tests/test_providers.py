"""Unit tests for app/providers.py streaming and JSON utilities."""

from __future__ import annotations

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from app.providers import PlannerProvider
    return PlannerProvider(model="openrouter/test-model")


def _sse_lines(*chunks: dict) -> list[str]:
    """Convert dicts to SSE 'data: ...' lines followed by [DONE]."""
    lines = [f"data: {json.dumps(c)}" for c in chunks]
    lines.append("data: [DONE]")
    return lines


@pytest.mark.asyncio
async def test_stream_chat_single_tool_call(provider, monkeypatch):
    """Single tool call (existing behaviour) still works."""
    sse = _sse_lines(
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "read_file", "arguments": '{"path":'}}]}, "finish_reason": None}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"foo.txt"}'}}]}, "finish_reason": "tool_calls"}]},
    )

    async def fake_aiter_lines():
        for line in sse:
            yield line

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = fake_aiter_lines

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)

    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.providers.httpx.AsyncClient", return_value=mock_client_cm):
        events = [e async for e in provider.stream_chat_with_tools("sys", [{"role": "user", "content": "go"}], [])]

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "read_file"
    assert tool_calls[0]["args"] == {"path": "foo.txt"}


@pytest.mark.asyncio
async def test_stream_chat_multiple_tool_calls(provider, monkeypatch):
    """Two parallel tool calls in one response — both must be emitted in index order."""
    sse = _sse_lines(
        # First chunk: names for both tool_calls
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "read_file", "arguments": '{"path":'}},
            {"index": 1, "id": "c2", "function": {"name": "run_command", "arguments": '{"cmd":'}},
        ]}, "finish_reason": None}]},
        # Second chunk: finish args for both
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '"a.txt"}'}},
            {"index": 1, "function": {"arguments": '"ls"}'}},
        ]}, "finish_reason": "tool_calls"}]},
    )

    async def fake_aiter_lines():
        for line in sse:
            yield line

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = fake_aiter_lines

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)

    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.providers.httpx.AsyncClient", return_value=mock_client_cm):
        events = [e async for e in provider.stream_chat_with_tools("sys", [{"role": "user", "content": "go"}], [])]

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) == 2
    assert tool_calls[0]["name"] == "read_file"
    assert tool_calls[0]["args"] == {"path": "a.txt"}
    assert tool_calls[1]["name"] == "run_command"
    assert tool_calls[1]["args"] == {"cmd": "ls"}


def _make_client_cm_for_resp(mock_resp):
    """Wrap a mock response in the nested async context managers httpx expects."""
    stream_cm = AsyncMock()
    stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    stream_cm.__aexit__ = AsyncMock(return_value=False)

    client = AsyncMock()
    client.stream = MagicMock(return_value=stream_cm)

    client_cm = AsyncMock()
    client_cm.__aenter__ = AsyncMock(return_value=client)
    client_cm.__aexit__ = AsyncMock(return_value=False)
    return client_cm


@pytest.mark.asyncio
async def test_stream_chat_fallback_emits_provider_info(monkeypatch):
    """When primary model returns 429, fallback yields provider_info before streaming."""
    import httpx as _httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from app.providers import PlannerProvider
    provider = PlannerProvider(model="openrouter/primary-model")

    monkeypatch.setattr(provider, "_openrouter_models_to_try",
                        lambda *a, **kw: ["primary-model", "fallback-model"])

    # Primary: 429 — httpx raises HTTPStatusError
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.raise_for_status = MagicMock(
        side_effect=_httpx.HTTPStatusError("429", request=MagicMock(), response=MagicMock(status_code=429))
    )

    # Fallback: 200 + text_only stop
    fallback_sse = _sse_lines({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})

    async def fake_aiter():
        for line in fallback_sse:
            yield line

    mock_200 = AsyncMock()
    mock_200.status_code = 200
    mock_200.raise_for_status = MagicMock()
    mock_200.aiter_lines = fake_aiter

    client_cms = iter([_make_client_cm_for_resp(mock_429), _make_client_cm_for_resp(mock_200)])

    with patch("app.providers.httpx.AsyncClient", side_effect=lambda **kw: next(client_cms)):
        events = [e async for e in provider.stream_chat_with_tools("sys", [{"role": "user", "content": "go"}], [])]

    pinfo = [e for e in events if e.get("type") == "provider_info"]
    assert len(pinfo) == 1
    assert pinfo[0]["model"] == "fallback-model"
    assert pinfo[0]["fallback"] is True


def test_allowed_models_whitelist_blocks_disallowed_model(monkeypatch):
    """ALLOWED_MODELS env var prevents disallowed models from entering the fallback chain."""
    monkeypatch.setenv("ALLOWED_MODELS", "claude-3-5-sonnet,gpt-4")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from importlib import reload
    import app.providers as _prov
    reload(_prov)
    p = _prov.PlannerProvider(model="google/gemma-4-31b-it:free")
    with pytest.raises(ValueError, match="ALLOWED_MODELS"):
        p._openrouter_models_to_try("google/gemma-4-31b-it:free")


def test_allowed_models_empty_allows_all(monkeypatch):
    """Unset ALLOWED_MODELS permits all models (backward compatible)."""
    monkeypatch.delenv("ALLOWED_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from importlib import reload
    import app.providers as _prov
    reload(_prov)
    p = _prov.PlannerProvider(model="google/gemma-4-31b-it:free")
    result = p._openrouter_models_to_try("google/gemma-4-31b-it:free")
    assert "google/gemma-4-31b-it:free" in result


def test_free_tiers_track_current_benchmark_defaults():
    from app.providers import MODEL_TIERS

    assert MODEL_TIERS["uia"][0] == "openai/gpt-oss-120b:free"
    assert "minimax/minimax-m2.5:free" not in MODEL_TIERS["balanced"]


def test_allowed_models_permits_matching_model(monkeypatch):
    """Requests matching the allow-list succeed; non-matching fallbacks are stripped."""
    monkeypatch.setenv("ALLOWED_MODELS", "google/gemma-4-31b-it:free")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from importlib import reload
    import app.providers as _prov
    reload(_prov)
    p = _prov.PlannerProvider(model="google/gemma-4-31b-it:free")
    result = p._openrouter_models_to_try("google/gemma-4-31b-it:free")
    assert result == ["google/gemma-4-31b-it:free"]


def test_allowed_models_supports_glob_patterns(monkeypatch):
    monkeypatch.setenv("ALLOWED_MODELS", "google/gemma-*:free,meta-llama/*")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from importlib import reload
    import app.providers as _prov

    reload(_prov)
    p = _prov.PlannerProvider(model="google/gemma-4-31b-it:free")
    result = p._openrouter_models_to_try("google/gemma-4-31b-it:free")
    assert "google/gemma-4-31b-it:free" in result
    assert "google/gemma-4-26b-a4b-it:free" in result
    assert "meta-llama/llama-3.3-70b-instruct:free" in result
    assert "nvidia/nemotron-3-super-120b-a12b:free" not in result


def test_ollama_model_requires_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from app.providers import PlannerProvider

    p = PlannerProvider(model="ollama/llama3.2")
    assert p._is_ollama()
    assert p.model == "ollama/llama3.2"


# ── Chain-retry (AI-16) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chain_retry_all_429_raises_friendly_message(monkeypatch):
    """When every chain attempt exhausts all models with 429, a friendly
    RuntimeError is raised (never a raw httpx error) and the retry status
    event is emitted before each backoff sleep."""
    import asyncio as _asyncio
    import httpx as _httpx
    from app.providers import PlannerProvider, _CHAIN_RETRY_MAX, _CHAIN_RETRY_BACKOFFS

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = PlannerProvider(model="openrouter/test-model")

    call_count = 0

    async def _always_429(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise _httpx.HTTPStatusError(
            "429", request=MagicMock(), response=MagicMock(status_code=429)
        )
        yield  # makes this an async generator

    monkeypatch.setattr(provider, "_stream_chat_with_tools_single", _always_429)

    sleep_calls: list[float] = []

    async def fake_sleep(n: float) -> None:
        sleep_calls.append(n)

    monkeypatch.setattr(_asyncio, "sleep", fake_sleep)

    collected: list[dict] = []
    with pytest.raises(RuntimeError, match="All free models are currently busy"):
        async for event in provider.stream_chat_with_tools(
            "sys", [{"role": "user", "content": "hi"}], []
        ):
            collected.append(event)

    # Total attempts == max retries + 1
    assert call_count == _CHAIN_RETRY_MAX + 1
    # Friendly retry events emitted before each backoff
    retry_events = [e for e in collected if e.get("retrying")]
    assert len(retry_events) == _CHAIN_RETRY_MAX
    assert all("All free models are busy" in e["message"] for e in retry_events)
    # Sleep durations match the configured backoffs
    assert sleep_calls == list(_CHAIN_RETRY_BACKOFFS)


@pytest.mark.asyncio
async def test_chain_retry_succeeds_on_second_attempt(monkeypatch):
    """First chain attempt 429s; second attempt succeeds — task completes normally."""
    import asyncio as _asyncio
    import httpx as _httpx
    from app.providers import PlannerProvider

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = PlannerProvider(model="openrouter/test-model")

    call_count = 0

    async def _flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _httpx.HTTPStatusError(
                "429", request=MagicMock(), response=MagicMock(status_code=429)
            )
        yield {"type": "text_only", "content": "success"}

    monkeypatch.setattr(provider, "_stream_chat_with_tools_single", _flaky)
    monkeypatch.setattr(_asyncio, "sleep", AsyncMock())

    events = [
        e async for e in provider.stream_chat_with_tools(
            "sys", [{"role": "user", "content": "hi"}], []
        )
    ]

    assert call_count == 2
    assert any(e.get("content") == "success" for e in events)
    assert any(e.get("retrying") for e in events)


@pytest.mark.asyncio
async def test_chain_retry_skips_non_rate_limit_errors(monkeypatch):
    """A non-rate-limit HTTP error (e.g. 400) propagates immediately — no retry."""
    import httpx as _httpx
    from app.providers import PlannerProvider

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = PlannerProvider(model="openrouter/test-model")

    call_count = 0

    async def _bad_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise _httpx.HTTPStatusError(
            "400", request=MagicMock(), response=MagicMock(status_code=400)
        )
        yield

    monkeypatch.setattr(provider, "_stream_chat_with_tools_single", _bad_request)

    with pytest.raises(_httpx.HTTPStatusError):
        async for _ in provider.stream_chat_with_tools(
            "sys", [{"role": "user", "content": "hi"}], []
        ):
            pass

    # Only one attempt — no chain retry for non-rate-limit errors
    assert call_count == 1


@pytest.mark.asyncio
async def test_tool_partial_events_emitted_during_arg_streaming(provider, monkeypatch):
    """tool_partial events are yielded while tool-call args accumulate (AI-17)."""
    # Two chunks: first carries the tool name + partial args, second finishes them.
    sse = _sse_lines(
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "read_file", "arguments": '{"path":'}}]}, "finish_reason": None}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"foo.txt"}'}}]}, "finish_reason": "tool_calls"}]},
    )

    async def fake_aiter_lines():
        for line in sse:
            yield line

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = fake_aiter_lines

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)

    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.providers.httpx.AsyncClient", return_value=mock_client_cm):
        events = [e async for e in provider.stream_chat_with_tools("sys", [{"role": "user", "content": "go"}], [])]

    partial_events = [e for e in events if e["type"] == "tool_partial"]
    tool_call_events = [e for e in events if e["type"] == "tool_call"]

    # At least one tool_partial emitted during arg streaming
    assert len(partial_events) >= 1
    assert partial_events[0]["name"] == "read_file"
    assert isinstance(partial_events[0]["args_partial"], str)

    # Final tool_call still emitted with complete args
    assert len(tool_call_events) == 1
    assert tool_call_events[0]["args"] == {"path": "foo.txt"}


# ── AI-22: BLOCKED_MODELS / BLOCKED_PROVIDERS ──────────────────────────────

def test_blocked_models_glob_blocks_matching_model(monkeypatch):
    """BLOCKED_MODELS with a glob pattern blocks matching models."""
    monkeypatch.setenv("BLOCKED_MODELS", "*minimax*")
    monkeypatch.delenv("ALLOWED_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from importlib import reload
    import app.providers as _prov
    reload(_prov)
    p = _prov.PlannerProvider(model="google/gemma-4-31b-it:free")
    with pytest.raises(ValueError, match="blocked"):
        p._openrouter_models_to_try("minimax/minimax-m1:extended")


def test_blocked_providers_blocks_entire_provider(monkeypatch):
    """BLOCKED_PROVIDERS removes all models from a named provider."""
    monkeypatch.setenv("BLOCKED_PROVIDERS", "google")
    monkeypatch.delenv("ALLOWED_MODELS", raising=False)
    monkeypatch.delenv("BLOCKED_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from importlib import reload
    import app.providers as _prov
    reload(_prov)
    p = _prov.PlannerProvider(model="google/gemma-4-31b-it:free")
    with pytest.raises(ValueError, match="blocked"):
        p._openrouter_models_to_try("google/gemma-4-31b-it:free")


def test_blocked_models_empty_allows_all(monkeypatch):
    """Unset BLOCKED_MODELS/BLOCKED_PROVIDERS permits all models (default)."""
    monkeypatch.delenv("BLOCKED_MODELS", raising=False)
    monkeypatch.delenv("BLOCKED_PROVIDERS", raising=False)
    monkeypatch.delenv("ALLOWED_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from importlib import reload
    import app.providers as _prov
    reload(_prov)
    p = _prov.PlannerProvider(model="google/gemma-4-31b-it:free")
    chain = p._openrouter_models_to_try("google/gemma-4-31b-it:free")
    assert len(chain) > 0


# ── AI-23: Thinking budget ────────────────────────────────────────────────────

def test_thinking_budget_default_is_off():
    """PlannerProvider.thinking_budget defaults to 'off'."""
    from app.providers import PlannerProvider
    p = PlannerProvider(model="anthropic/claude-3-haiku")
    assert p.thinking_budget == "off"


def test_thinking_budget_standard_adds_thinking_param(monkeypatch):
    """_chat_anthropic includes thinking param when budget is 'standard'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app.providers import PlannerProvider
    p = PlannerProvider(model="anthropic/claude-3-haiku")
    p.thinking_budget = "standard"

    captured = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

    def fake_post(url, headers=None, json=None, **kw):
        captured["payload"] = json
        return FakeResp()

    p._http_client.post = fake_post
    result = p._chat_anthropic("sys", "prompt")
    assert result == "ok"
    assert "thinking" in captured["payload"]
    assert captured["payload"]["thinking"]["type"] == "enabled"
    assert captured["payload"]["thinking"]["budget_tokens"] == 5000


def test_thinking_budget_extended_uses_larger_budget(monkeypatch):
    """_chat_anthropic uses 16 000 budget_tokens when 'extended'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app.providers import PlannerProvider
    p = PlannerProvider(model="anthropic/claude-3-haiku")
    p.thinking_budget = "extended"

    captured = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "deep"}], "usage": {}}

    def fake_post(url, headers=None, json=None, **kw):
        captured["payload"] = json
        return FakeResp()

    p._http_client.post = fake_post
    result = p._chat_anthropic("sys", "prompt")
    assert result == "deep"
    assert captured["payload"]["thinking"]["budget_tokens"] == 16000


def test_thinking_budget_off_omits_thinking_param(monkeypatch):
    """_chat_anthropic omits the thinking key when budget is 'off'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app.providers import PlannerProvider
    p = PlannerProvider(model="anthropic/claude-3-haiku")
    p.thinking_budget = "off"

    captured = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"content": [{"type": "text", "text": "plain"}], "usage": {}}

    def fake_post(url, headers=None, json=None, **kw):
        captured["payload"] = json
        return FakeResp()

    p._http_client.post = fake_post
    p._chat_anthropic("sys", "prompt")
    assert "thinking" not in captured["payload"]


# ── Constrained decoding (json_mode) + tool-call arg integrity ───────────────

def _mock_async_client_for(sse_lines):
    """Build a patched httpx.AsyncClient context manager that streams sse_lines."""
    from unittest.mock import AsyncMock, MagicMock

    async def fake_aiter_lines():
        for line in sse_lines:
            yield line

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = fake_aiter_lines

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)

    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_client_cm


@pytest.mark.asyncio
async def test_tool_call_with_unparseable_args_flags_args_error(provider):
    """Busted JSON args must NOT silently execute as {} — the event carries
    args_error so the agent bounces it back to the model."""
    sse = _sse_lines(
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "write_file", "arguments": "not json at all {{{"}}]}, "finish_reason": None}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    )
    with patch("app.providers.httpx.AsyncClient", return_value=_mock_async_client_for(sse)):
        events = [e async for e in provider.stream_chat_with_tools("sys", [{"role": "user", "content": "go"}], [])]

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["args"] == {}
    assert tool_calls[0].get("args_error")


def test_chat_groq_json_mode_sets_response_format(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    from app.providers import PlannerProvider
    p = PlannerProvider(model="groq/llama-3.3-70b-versatile")
    seen = {}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\": true}"}}]}

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, headers=None, json=None):
            seen["payload"] = json
            return FakeResp()

    monkeypatch.setattr("app.providers.httpx.Client", FakeClient)
    out = p._chat_groq("Return ONLY valid JSON", "prompt", json_mode=True)
    assert seen["payload"]["response_format"] == {"type": "json_object"}
    assert out == "{\"ok\": true}"

    seen.clear()
    p._chat_groq("sys", "prompt", json_mode=False)
    assert "response_format" not in seen["payload"]


def test_call_llm_retries_without_json_mode_on_400(monkeypatch):
    """Models that reject response_format must not kill the call — retry plain."""
    import httpx as _httpx
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from app.providers import PlannerProvider
    p = PlannerProvider(model="groq/llama-3.3-70b-versatile")
    calls = []

    def fake_groq(system, prompt, screenshot_b64=None, json_mode=False):
        calls.append(json_mode)
        if json_mode:
            req = _httpx.Request("POST", "http://test")
            raise _httpx.HTTPStatusError("bad request", request=req, response=_httpx.Response(400, request=req))
        return "{\"complete\": true}"

    monkeypatch.setattr(p, "_chat_groq", fake_groq)
    out = p._call_llm("sys", "prompt", json_mode=True)
    assert calls == [True, False]
    assert out == "{\"complete\": true}"


# ── Swarm racing: parallel free providers, fastest valid stream wins ─────────

@pytest.mark.asyncio
async def test_swarm_race_streams_fastest_provider(monkeypatch):
    import asyncio
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "ok")
    from app.providers import PlannerProvider
    p = PlannerProvider(model="groq/llama-3.3-70b-versatile")
    assert p._swarm_race_enabled() is True

    async def fake_single(system, messages, tools, screenshot_b64=None, model_override=None):
        if model_override is None:   # groq primary — slow today
            await asyncio.sleep(0.25)
            yield {"type": "tool_call", "id": "g", "name": "slow_tool", "args": {}, "thought": ""}
        else:                        # openrouter chain — fast
            await asyncio.sleep(0.01)
            yield {"type": "thought", "content": "fast thinking"}
            yield {"type": "tool_call", "id": "o", "name": "fast_tool", "args": {}, "thought": ""}

    monkeypatch.setattr(p, "_stream_chat_with_tools_single", fake_single)
    events = [e async for e in p.stream_chat_with_tools("sys", [{"role": "user", "content": "go"}], [])]

    winners = [e for e in events if e.get("race_winner")]
    assert winners and winners[0]["race_winner"] == "openrouter"
    names = [e["name"] for e in events if e.get("type") == "tool_call"]
    assert names == ["fast_tool"], f"only the winner streams: {events}"


@pytest.mark.asyncio
async def test_swarm_race_survives_one_provider_failing(monkeypatch):
    import asyncio
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "ok")
    from app.providers import PlannerProvider
    p = PlannerProvider(model="groq/llama-3.3-70b-versatile")

    async def fake_single(system, messages, tools, screenshot_b64=None, model_override=None):
        if model_override is None:   # groq hard-down
            raise RuntimeError("groq 429 rate limited")
            yield  # pragma: no cover — makes this an async generator
        await asyncio.sleep(0.01)
        yield {"type": "tool_call", "id": "o", "name": "rescue_tool", "args": {}, "thought": ""}

    monkeypatch.setattr(p, "_stream_chat_with_tools_single", fake_single)
    events = [e async for e in p.stream_chat_with_tools("sys", [{"role": "user", "content": "go"}], [])]
    names = [e["name"] for e in events if e.get("type") == "tool_call"]
    assert names == ["rescue_tool"]
    winners = [e for e in events if e.get("race_winner")]
    assert winners and winners[0]["race_winner"] == "openrouter"


def test_swarm_race_gating(monkeypatch):
    from app.providers import PlannerProvider
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "ok")
    assert PlannerProvider(model="groq/llama-3.3-70b-versatile")._swarm_race_enabled() is True
    # Kill switch.
    monkeypatch.setenv("ORYNN_SWARM_RACE", "0")
    assert PlannerProvider(model="groq/llama-3.3-70b-versatile")._swarm_race_enabled() is False
    monkeypatch.delenv("ORYNN_SWARM_RACE")
    # No second provider → no race.
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert PlannerProvider(model="groq/llama-3.3-70b-versatile")._swarm_race_enabled() is False


def test_swarm_race_all_mode_openrouter_only(monkeypatch):
    """ORYNN_SWARM_RACE=all unlocks same-provider racing when OpenRouter is
    the only key — two DIFFERENT free models race on one provider."""
    from app.providers import PlannerProvider, DEFAULT_OPENROUTER_MODEL
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "ok")
    monkeypatch.delenv("ORYNN_SWARM_RACE", raising=False)

    # Default 'cross' mode: single provider → no race (quota discipline).
    p = PlannerProvider(model=DEFAULT_OPENROUTER_MODEL)
    assert p._swarm_race_mode() == "cross"
    assert p._swarm_race_enabled() is False

    # Opt-in 'all' mode: race two different OpenRouter free models.
    monkeypatch.setenv("ORYNN_SWARM_RACE", "all")
    p = PlannerProvider(model=DEFAULT_OPENROUTER_MODEL)
    assert p._swarm_race_mode() == "all"
    assert p._swarm_race_enabled() is True
    cands = p._race_candidates()
    assert len(cands) == 2
    assert cands[0] == ("primary", None)
    alt_label, alt_model = cands[1]
    # The alternate must be a genuinely different model than the primary.
    assert alt_model is not None
    assert alt_model.replace("openrouter/", "") != p.model.replace("openrouter/", "")
    assert alt_label and alt_label != "primary"

    # Kill switch still wins over everything.
    monkeypatch.setenv("ORYNN_SWARM_RACE", "0")
    p = PlannerProvider(model=DEFAULT_OPENROUTER_MODEL)
    assert p._swarm_race_mode() == "off"
    assert p._swarm_race_enabled() is False


def test_swarm_race_all_mode_does_not_break_cross(monkeypatch):
    """'all' with both keys keeps the proven cross-provider pair."""
    from app.providers import PlannerProvider
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "ok")
    monkeypatch.setenv("ORYNN_SWARM_RACE", "all")
    p = PlannerProvider(model="groq/llama-3.3-70b-versatile")
    assert p._swarm_race_enabled() is True
    labels = [label for label, _ in p._race_candidates()]
    assert labels == ["groq", "openrouter"]
