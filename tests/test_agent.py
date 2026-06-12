import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.agent import AgentService
from pathlib import Path

@pytest.mark.asyncio
async def test_action_parser():
    engine = AgentService(workspace=Path("."), log_emitter=MagicMock())
    
    # We can test the extraction logic directly if we extract it, 
    # but since it's buried in run_task stream loop, let's mock the stream.
    # We will test using mock_stream.
    
    mock_provider = MagicMock()
    
    async def mock_stream_chat(*args, **kwargs):
        yield '<thought>I should run a command</thought>\n'
        yield '<action type="run_command">\n'
        yield '{"command": "echo hello"}\n'
        yield '</action>\n'
        yield '<action type="finish">{"reason":"done"}</action>'

    mock_provider.stream_chat = mock_stream_chat

    events = []
    engine._emit = AsyncMock(side_effect=lambda task_id, type, data: events.append((type, data)))
    engine._emit_reasoning = AsyncMock()

    with patch('app.agent.PlannerProvider', return_value=mock_provider):
        await engine.run_task("test_task_id", "Run a test command", mock_provider)

    action_starts = [e for e in events if e[0] == "action_start"]
    assert len(action_starts) >= 1
    assert action_starts[0][1]["action_type"] == "run_command"

@pytest.mark.asyncio
async def test_delegate_parser():
    engine = AgentService(workspace=Path("."), log_emitter=MagicMock())
    mock_provider = MagicMock()
    
    async def mock_stream_chat(*args, **kwargs):
        yield '<thought>I will delegate now.</thought>\n'
        yield '<delegate model="gpt-4o-mini">\n'
        yield '<thought>Delegating this step</thought>\n'
        yield '<task>Write a haiku</task>\n'
        yield '</delegate>\n'
        yield '<action type="finish">{"reason":"done"}</action>'

    mock_provider.stream_chat = mock_stream_chat

    events = []
    engine._emit = AsyncMock(side_effect=lambda task_id, type, data: events.append((type, data)))
    engine._emit_reasoning = AsyncMock()

    # To avoid the actual sub-agent running in the background and hitting the network,
    # we patch asyncio.to_thread where it calls the sub-agent's call_llm.
    with patch('app.agent.PlannerProvider', return_value=mock_provider), \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        mock_to_thread.return_value = "Here is a haiku."
        await engine.run_task("test_delegate_id", "Run a test delegate", mock_provider)

    action_starts = [e for e in events if e[0] == "action_start"]
    assert len(action_starts) >= 1
    assert action_starts[0][1]["action_type"] == "delegate"
    
    action_results = [e for e in events if e[0] == "action_result"]
    assert len(action_results) >= 1
    assert action_results[0][1]["action_type"] == "delegate"
    assert action_results[0][1]["output"] == "Here is a haiku."



def test_coerce_history_trims_cleanly_for_small_models():
    """Free models derail on mid-word cuts and dangling code fences — long
    turns must be trimmed at a line boundary, fences closed, and the cut
    flagged so the model knows context is missing."""
    from app.agent import _coerce_history_messages

    long_code = "intro line\n```python\n" + ("x = 1\n" * 600)
    out = _coerce_history_messages([
        {"role": "user", "content": long_code},
        {"role": "assistant", "content": "short reply"},
    ])

    assert len(out) == 2
    trimmed = out[0]["content"]
    assert trimmed.endswith("…[earlier content trimmed]")
    assert trimmed.count("```") % 2 == 0          # no dangling fence
    body = trimmed.rsplit("…", 1)[0]
    assert all(line in long_code or line in ("```", "") for line in body.splitlines())

    # Short turns pass through untouched.
    assert out[1]["content"] == "short reply"


def test_coerce_history_keeps_only_user_assistant_turns():
    from app.agent import _coerce_history_messages

    out = _coerce_history_messages([
        {"role": "system", "content": "ignore me"},
        {"role": "user", "content": "hi"},
        "not-a-dict",
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "hello"},
    ])
    assert [(m["role"], m["content"]) for m in out] == [("user", "hi"), ("assistant", "hello")]


@pytest.mark.asyncio
async def test_parallel_tool_calls_batch_without_extra_model_round_trips(tmp_path):
    """When the model emits several tool calls in ONE turn, every call must
    execute (previously all but the last were silently dropped) and the queued
    ones must run WITHOUT another model round-trip — the free-tier speed win."""
    engine = AgentService(workspace=tmp_path, log_emitter=MagicMock())
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")

    model_calls = {"n": 0}

    async def fake_tools_stream(system, messages, tools, screenshot_b64=None):
        model_calls["n"] += 1
        if model_calls["n"] == 1:
            yield {"type": "tool_call", "id": "c1", "name": "read_file", "args": {"path": "a.txt"}, "thought": "read both"}
            yield {"type": "tool_call", "id": "c2", "name": "read_file", "args": {"path": "b.txt"}, "thought": ""}
        else:
            yield {"type": "tool_call", "id": "c3", "name": "finish", "args": {"reason": "done"}, "thought": "done"}

    mock_provider = MagicMock()
    mock_provider.stream_chat_with_tools = fake_tools_stream
    mock_provider.total_tokens = 0
    mock_provider._total_input_tokens = 0
    mock_provider._total_output_tokens = 0

    events = []
    engine._emit = AsyncMock(side_effect=lambda task_id, type, data: events.append((type, data)))
    engine._emit_reasoning = AsyncMock()

    with patch("app.agent.PlannerProvider", return_value=mock_provider):
        await engine.run_task("batch_task", "read both files", mock_provider)

    results = [e[1] for e in events if e[0] == "action_result"]
    read_results = [r for r in results if r.get("action_type") == "read_file"]
    assert len(read_results) == 2, f"both batched reads must execute, saw: {results}"
    assert all(r["ok"] for r in read_results)
    # 3 actions (read, read, finish) in only 2 model calls — the queued read
    # executed without a round-trip.
    assert model_calls["n"] == 2


@pytest.mark.asyncio
async def test_workflow_compiler_records_then_replays_with_one_model_call(tmp_path, monkeypatch):
    """INSANE item #2: the first successful run compiles to a trace; the second
    run of the same goal replays it action-by-action with ZERO model calls
    until the final verify+finish turn."""
    monkeypatch.setenv("ORYNN_TRACE_STORE", str(tmp_path / "traces.json"))
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "a.txt").write_text("alpha", encoding="utf-8")
    (ws / "b.txt").write_text("beta", encoding="utf-8")

    def make_provider(counter):
        calls = {"n": 0}
        async def stream(system, messages, tools, screenshot_b64=None):
            calls["n"] += 1
            if calls["n"] == 1 and counter == "first-run":
                yield {"type": "tool_call", "id": "c1", "name": "read_file", "args": {"path": "a.txt"}, "thought": "read a"}
            elif calls["n"] == 2 and counter == "first-run":
                yield {"type": "tool_call", "id": "c2", "name": "read_file", "args": {"path": "b.txt"}, "thought": "read b"}
            else:
                yield {"type": "tool_call", "id": "cf", "name": "finish", "args": {"reason": "both read"}, "thought": "done"}
        p = MagicMock()
        p.stream_chat_with_tools = stream
        p.total_tokens = 0; p._total_input_tokens = 0; p._total_output_tokens = 0
        return p, calls

    GOAL = "read both data files please"

    # ── Run 1: live planning (3 model calls) — compiles the trace on finish.
    engine1 = AgentService(workspace=ws, log_emitter=MagicMock())
    p1, calls1 = make_provider("first-run")
    engine1._emit = AsyncMock()
    engine1._emit_reasoning = AsyncMock()
    with patch("app.agent.PlannerProvider", return_value=p1):
        await engine1.run_task("compile-run", GOAL, p1)
    assert calls1["n"] == 3
    # run_task defaults to mode="coding" — the trace compiles under that key.
    assert engine1.trace_store.find_exact(GOAL, "coding") is not None

    # ── Run 2: same goal replays — the model is consulted exactly ONCE.
    engine2 = AgentService(workspace=ws, log_emitter=MagicMock())
    p2, calls2 = make_provider("replay-run")
    events = []
    engine2._emit = AsyncMock(side_effect=lambda task_id, type, data: events.append((type, data)))
    engine2._emit_reasoning = AsyncMock()
    with patch("app.agent.PlannerProvider", return_value=p2):
        await engine2.run_task("replay-run", GOAL, p2)

    results = [e[1] for e in events if e[0] == "action_result" and e[1].get("action_type") == "read_file"]
    assert len(results) == 2, f"replayed actions must execute: {results}"
    assert all(r["ok"] for r in results)
    assert calls2["n"] == 1, "replay must only consult the model for the final verify+finish"
    statuses = " | ".join(str(e[1].get("message", "")) for e in events if e[0] == "status")
    assert "Replaying a previously successful run" in statuses


@pytest.mark.asyncio
async def test_workflow_compiler_divergence_invalidates_and_recovers(tmp_path, monkeypatch):
    """A replayed action that fails retires the trace and hands control back
    to live planning — the task still completes."""
    monkeypatch.setenv("ORYNN_TRACE_STORE", str(tmp_path / "traces.json"))
    ws = tmp_path / "ws"; ws.mkdir()

    from app.trace_store import TraceStore
    store = TraceStore()
    GOAL = "read the special data file"
    store.save(GOAL, "coding", [
        {"type": "read_file", "args": {"path": "missing.txt"}},
        {"type": "read_file", "args": {"path": "also-missing.txt"}},
    ])

    calls = {"n": 0}
    async def stream(system, messages, tools, screenshot_b64=None):
        calls["n"] += 1
        yield {"type": "tool_call", "id": "cf", "name": "finish", "args": {"reason": "recovered"}, "thought": "recover"}
    p = MagicMock()
    p.stream_chat_with_tools = stream
    p.total_tokens = 0; p._total_input_tokens = 0; p._total_output_tokens = 0

    engine = AgentService(workspace=ws, log_emitter=MagicMock())
    events = []
    engine._emit = AsyncMock(side_effect=lambda task_id, type, data: events.append((type, data)))
    engine._emit_reasoning = AsyncMock()
    with patch("app.agent.PlannerProvider", return_value=p):
        await engine.run_task("diverge-run", GOAL, p)

    statuses = " | ".join(str(e[1].get("message", "")) for e in events if e[0] == "status")
    assert "Replay diverged" in statuses
    assert engine.trace_store.find_exact(GOAL, "coding") is None
    assert calls["n"] >= 1  # live planning took over and finished
    dones = [e for e in events if e[0] == "done"]
    assert dones and dones[-1][1].get("complete") is True
