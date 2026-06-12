"""Groq is the preferred free provider when its key is set (sub-second latency),
with a transparent fallback to the OpenRouter ":free" chain so the speed win never
costs reliability. Covers both halves: auto-selection precedence + the streaming
cross-provider fallback on a Groq failure.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Half 1 — precedence in auto model-selection (_select_model_for_task)
# ---------------------------------------------------------------------------

def test_groq_preferred_over_openrouter_when_both_set(monkeypatch):
    """Both keys set → Groq wins (free AND sub-second; the app's #1 UX win)."""
    from app.main import _select_model_for_task

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("DESKTOP_MODEL", raising=False)

    sel = _select_model_for_task("read the windows version", mode="auto")
    assert sel["selected_model"].startswith("groq/"), sel
    assert sel["model_source"] == "auto:groq"
    assert sel["required_key"] == "GROQ_API_KEY"


def test_openrouter_used_when_no_groq_key(monkeypatch):
    """No Groq key → the previous OpenRouter-first behaviour is unchanged."""
    from app.main import _select_model_for_task

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    sel = _select_model_for_task("read the windows version", mode="auto")
    assert not sel["selected_model"].startswith("groq/"), sel
    assert sel["required_key"] == "OPENROUTER_API_KEY"


def test_explicit_desktop_model_still_wins_over_groq(monkeypatch):
    """A deliberate DESKTOP_MODEL opt-in (reliability) still wins for an explicit
    desktop task, even when Groq is set — that escape hatch is about reliability."""
    from app.main import _select_model_for_task

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("DESKTOP_MODEL", "z-ai/glm-4.5-air:free")

    sel = _select_model_for_task("click the Start button", mode="computer")
    assert sel["selected_model"] == "z-ai/glm-4.5-air:free", sel
    assert not sel["selected_model"].startswith("groq/")


# ---------------------------------------------------------------------------
# Half 2 — cross-provider fallback on a Groq failure (stream_chat_with_tools)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_failure_falls_back_to_openrouter(monkeypatch):
    """A Groq failure must never cost the user the step. With swarm racing the
    OpenRouter candidate is ALREADY in flight when Groq 429s, so it wins the
    race outright — no model swap, no backoff, answer still arrives."""
    import httpx as _httpx
    from app.providers import PlannerProvider, DEFAULT_OPENROUTER_MODEL

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    provider = PlannerProvider(model="groq/llama-3.3-70b-versatile")

    calls: list[str] = []

    async def _by_model(*args, **kwargs):
        effective = kwargs.get("model_override") or provider.model
        calls.append(effective)
        if effective.startswith("groq/"):
            raise _httpx.HTTPStatusError(
                "429", request=MagicMock(), response=MagicMock(status_code=429)
            )
            yield  # makes this an async generator
        yield {"type": "text_only", "content": "openrouter-success"}

    monkeypatch.setattr(provider, "_stream_chat_with_tools_single", _by_model)

    events = [
        e async for e in provider.stream_chat_with_tools(
            "sys", [{"role": "user", "content": "hi"}], []
        )
    ]

    # Both providers were raced; Groq failed, OpenRouter delivered.
    assert any(c.startswith("groq/") for c in calls)
    assert DEFAULT_OPENROUTER_MODEL in calls
    assert any(e.get("race_winner") == "openrouter" for e in events)
    assert any(e.get("content") == "openrouter-success" for e in events)
    # The fast model is never swapped away — next step races Groq again.
    assert provider.model == "groq/llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_groq_without_openrouter_key_has_no_cross_provider_fallback(monkeypatch):
    """Without an OpenRouter key there's nothing to fall back to: the Groq error
    runs the normal chain-retry and surfaces the friendly busy message, and the
    model is never swapped away from Groq."""
    import asyncio as _asyncio
    import httpx as _httpx
    from app.providers import PlannerProvider

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = PlannerProvider(model="groq/llama-3.3-70b-versatile")

    async def _always_429(*args, **kwargs):
        raise _httpx.HTTPStatusError(
            "429", request=MagicMock(), response=MagicMock(status_code=429)
        )
        yield

    monkeypatch.setattr(provider, "_stream_chat_with_tools_single", _always_429)

    async def _fake_sleep(n):
        return None

    monkeypatch.setattr(_asyncio, "sleep", _fake_sleep)

    events: list[dict] = []
    with pytest.raises(RuntimeError, match="All free models are currently busy"):
        async for event in provider.stream_chat_with_tools(
            "sys", [{"role": "user", "content": "hi"}], []
        ):
            events.append(event)

    # No cross-provider fallback notice, and the model stayed on Groq.
    assert not any(e.get("fallback") for e in events)
    assert provider.model == "groq/llama-3.3-70b-versatile"
