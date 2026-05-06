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
