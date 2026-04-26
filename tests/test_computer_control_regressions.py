import asyncio
import sys
import types
import json

import pytest
import httpx

from app.agent import AgentService
from app.log_emitter import LogEmitter
from app.providers import PlannerProvider, detect_task_mode, infer_isolated_app_name


class DummyLogEmitter:
    async def emit(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_isolated_mode_waits_for_target_window_instead_of_falling_back(monkeypatch, workspace):
    service = AgentService(workspace, log_emitter=DummyLogEmitter())

    monkeypatch.setattr("app.agent.classify_task_complexity", lambda goal: "complex")
    monkeypatch.setattr("app.agent._get_hwnd_for_title", lambda title: None)
    monkeypatch.setattr("app.agent._capture_screenshot_b64", lambda sw, sh: "fake-shot")
    monkeypatch.setattr("app.agent._get_active_window_rect", lambda sw, sh: None)
    monkeypatch.setattr(service.memory, "search", lambda goal, limit=5: [])
    monkeypatch.setitem(
        sys.modules,
        "win32gui",
        types.SimpleNamespace(
            GetForegroundWindow=lambda: 0,
            IsWindowVisible=lambda hwnd: False,
            GetWindowText=lambda hwnd: "",
        ),
    )

    class FakeProvider:
        total_tokens = 0
        first_message = None

        async def stream_chat_with_tools(self, system, messages, tools, screenshot_b64=None):
            self.first_message = messages[0]["content"]
            yield {"type": "tool_call", "id": "call-1", "name": "finish", "args": {"reason": "done"}, "thought": ""}

    provider = FakeProvider()
    monkeypatch.setattr("app.agent.PlannerProvider", lambda model=None: provider)

    events = []

    async def capture_event(task_id, event_type, data):
        events.append((event_type, data))

    async def capture_reasoning(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_emit", capture_event)
    monkeypatch.setattr(service, "_emit_reasoning", capture_reasoning)
    monkeypatch.setattr(service, "_finalize", lambda *args, **kwargs: None)

    await service.run_task("task-1", "Open Notepad", mode="computer_isolated", isolated_app="Notepad")

    mode_events = [data for event, data in events if event == "mode"]
    status_messages = [data.get("message", "") for event, data in events if event == "status"]
    assert "Target window: Notepad" in provider.first_message
    assert any(event["mode"] == "computer_isolated" and event["isolated"] is True and event.get("isolated_pending") is True for event in mode_events)
    assert any("Waiting to attach isolated control to 'Notepad'" in message for message in status_messages)


@pytest.mark.asyncio
async def test_isolated_mode_passes_app_title_to_tool_executor(monkeypatch, workspace):
    service = AgentService(workspace, log_emitter=DummyLogEmitter())

    monkeypatch.setattr("app.agent.classify_task_complexity", lambda goal: "atomic")
    monkeypatch.setattr("app.agent._get_hwnd_for_title", lambda title: 1234)
    monkeypatch.setattr("app.providers._capture_hwnd_screenshot_b64", lambda hwnd: "fake-shot")
    monkeypatch.setattr(service.memory, "search", lambda goal, limit=5: [])

    captured = {}

    def fake_set_isolated_hwnd(hwnd, app_title=None):
        captured["hwnd"] = hwnd
        captured["app_title"] = app_title

    monkeypatch.setattr(service.tools, "set_isolated_hwnd", fake_set_isolated_hwnd)

    class FakeProvider:
        total_tokens = 0

        async def stream_chat_with_tools(self, system, messages, tools, screenshot_b64=None):
            yield {"type": "tool_call", "id": "call-1", "name": "finish", "args": {"reason": "done"}, "thought": ""}

    async def noop_emit(*args, **kwargs):
        return None

    monkeypatch.setattr("app.agent.PlannerProvider", lambda model=None: FakeProvider())
    monkeypatch.setattr(service, "_emit", noop_emit)
    monkeypatch.setattr(service, "_emit_reasoning", noop_emit)
    monkeypatch.setattr(service, "_finalize", lambda *args, **kwargs: None)

    await service.run_task("task-2", "Open Notepad", mode="computer_isolated", isolated_app="Notepad")

    assert captured == {"hwnd": 1234, "app_title": "Notepad"}


def test_providers_module_exposes_asyncio():
    import app.providers as providers

    assert providers.asyncio is not None


def test_single_app_desktop_goal_auto_selects_isolated_mode():
    assert infer_isolated_app_name("Open Notepad and write hello") == "Notepad"
    assert detect_task_mode("Open Notepad and write hello") == "computer_isolated"
    assert detect_task_mode("Open the Start menu and click the Settings button") == "computer"


def test_persistent_logs_omit_raw_screenshot_payload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    emitter = LogEmitter()
    screenshot_b64 = "a" * 10_000

    emitter.emit("task-log", "screenshot", {"data": screenshot_b64, "isolated": False})

    events = emitter.read_log("task-log")
    assert len(events) == 1
    assert events[0]["data"] == "[omitted from persistent log]"
    assert events[0]["data_omitted"] is True
    assert events[0]["data_chars"] == len(screenshot_b64)


@pytest.mark.asyncio
async def test_native_tool_stream_timeout_falls_back_to_xml(monkeypatch, workspace):
    service = AgentService(workspace, log_emitter=DummyLogEmitter())

    monkeypatch.setattr("app.agent.MODEL_STREAM_IDLE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr("app.agent.classify_task_complexity", lambda goal: "atomic")
    monkeypatch.setattr(service.memory, "search", lambda goal, limit=5: [])

    class FakeProvider:
        total_tokens = 0

        def __init__(self):
            self.native_calls = 0
            self.xml_calls = 0

        async def stream_chat_with_tools(self, system, messages, tools, screenshot_b64=None):
            self.native_calls += 1
            await asyncio.sleep(1)
            yield {"type": "tool_call", "id": "call-1", "name": "finish", "args": {"reason": "native"}, "thought": ""}

        async def stream_chat(self, system, messages, screenshot_b64=None):
            self.xml_calls += 1
            yield "Done via XML fallback."

    provider = FakeProvider()
    monkeypatch.setattr("app.agent.PlannerProvider", lambda model=None: provider)

    finalizations = []

    async def noop_emit(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_emit", noop_emit)
    monkeypatch.setattr(service, "_emit_reasoning", noop_emit)
    monkeypatch.setattr(service, "_finalize", lambda *args, **kwargs: finalizations.append(args))

    await service.run_task("task-timeout-fallback", "Say hello", mode="coding")

    assert provider.native_calls == 1
    assert provider.xml_calls == 1
    assert finalizations
    assert finalizations[-1][1] == "done"
    assert "Done via XML fallback." in finalizations[-1][2]


@pytest.mark.asyncio
async def test_xml_stream_timeout_fails_instead_of_hanging(monkeypatch, workspace):
    service = AgentService(workspace, log_emitter=DummyLogEmitter())

    monkeypatch.setattr("app.agent.MODEL_STREAM_IDLE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr("app.agent.classify_task_complexity", lambda goal: "atomic")
    monkeypatch.setattr(service.memory, "search", lambda goal, limit=5: [])

    class FakeProvider:
        total_tokens = 0

        async def stream_chat_with_tools(self, system, messages, tools, screenshot_b64=None):
            raise RuntimeError("native unavailable")
            yield

        async def stream_chat(self, system, messages, screenshot_b64=None):
            await asyncio.sleep(1)
            yield "This should never arrive."

    monkeypatch.setattr("app.agent.PlannerProvider", lambda model=None: FakeProvider())

    finalizations = []

    async def noop_emit(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_emit", noop_emit)
    monkeypatch.setattr(service, "_emit_reasoning", noop_emit)
    monkeypatch.setattr(service, "_finalize", lambda *args, **kwargs: finalizations.append(args))

    await service.run_task("task-timeout-fail", "Say hello", mode="coding")

    assert finalizations
    assert finalizations[-1][1] == "failed"
    assert "Timed out waiting for XML response from model." in finalizations[-1][2]


@pytest.mark.asyncio
async def test_xml_fallback_caps_recovery_steps(monkeypatch, workspace):
    service = AgentService(workspace, log_emitter=DummyLogEmitter())

    monkeypatch.setattr("app.agent.classify_task_complexity", lambda goal: "atomic")
    monkeypatch.setattr(service.memory, "search", lambda goal, limit=5: [])

    class FakeProvider:
        total_tokens = 0

        async def stream_chat_with_tools(self, system, messages, tools, screenshot_b64=None):
            raise RuntimeError("native unavailable")
            yield

        async def stream_chat(self, system, messages, screenshot_b64=None):
            yield '<thought>retry</thought><action type="bogus_tool">{}</action>'

    monkeypatch.setattr("app.agent.PlannerProvider", lambda model=None: FakeProvider())

    finalizations = []

    async def noop_emit(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_emit", noop_emit)
    monkeypatch.setattr(service, "_emit_reasoning", noop_emit)
    monkeypatch.setattr(service, "_finalize", lambda *args, **kwargs: finalizations.append(args))

    await service.run_task("task-xml-cap", "Say hello", mode="coding")

    assert finalizations
    assert finalizations[-1][1] == "failed"
    assert "XML fallback exhausted its max recovery steps." in finalizations[-1][2]


@pytest.mark.asyncio
async def test_openrouter_stream_chat_falls_back_to_second_model_on_429(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    provider = PlannerProvider(model="openrouter/google/gemma-4-31b-it:free")

    attempted_models = []

    class FakeStreamResponse:
        def __init__(self, status_code, lines):
            self.status_code = status_code
            self._lines = lines
            self.request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"status {self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

        async def aiter_lines(self):
            for line in self._lines:
                yield line

    class FakeStreamContext:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self.response

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeAsyncClient:
        def __init__(self, timeout=300):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None, json=None):
            payload = json
            attempted_models.append(payload["model"])
            if payload["model"] == "google/gemma-4-31b-it:free":
                return FakeStreamContext(FakeStreamResponse(429, []))

            lines = [
                f"data: {__import__('json').dumps({'choices': [{'delta': {'content': 'fallback ok'}}]})}",
                "data: [DONE]",
            ]
            return FakeStreamContext(FakeStreamResponse(200, lines))

    async def fast_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.providers.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.providers.asyncio.sleep", fast_sleep)

    chunks = []
    async for chunk in provider.stream_chat(
        "system",
        [{"role": "user", "content": "hello"}],
    ):
        chunks.append(chunk)

    assert attempted_models == [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
    ]
    assert "".join(chunks) == "fallback ok"


@pytest.mark.asyncio
async def test_xml_stream_normalizes_tool_history_for_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    provider = PlannerProvider(model="openrouter/google/gemma-4-26b-a4b-it:free")

    captured_payloads = []

    class FakeStreamResponse:
        def __init__(self, status_code, lines):
            self.status_code = status_code
            self._lines = lines
            self.request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"status {self.status_code}",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

        async def aiter_lines(self):
            for line in self._lines:
                yield line

    class FakeStreamContext:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self.response

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeAsyncClient:
        def __init__(self, timeout=300):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None, json=None):
            captured_payloads.append(json)
            lines = [
                f"data: {__import__('json').dumps({'choices': [{'delta': {'content': 'xml ok'}}]})}",
                "data: [DONE]",
            ]
            return FakeStreamContext(FakeStreamResponse(200, lines))

    monkeypatch.setattr("app.providers.httpx.AsyncClient", FakeAsyncClient)

    messages = [
        {"role": "assistant", "content": "I will open it.", "tool_calls": [
            {"id": "call-1", "type": "function", "function": {"name": "browser_open", "arguments": "{\"url\":\"http://127.0.0.1:8000\"}"}}
        ]},
        {"role": "tool", "tool_call_id": "call-1", "content": "Opened: http://127.0.0.1:8000/ | Title: AI Computer · Stream"},
        {"role": "user", "content": "Continue from here."},
    ]

    chunks = []
    async for chunk in provider.stream_chat("system", messages):
        chunks.append(chunk)

    assert "".join(chunks) == "xml ok"
    assert captured_payloads, "Expected stream_chat to make a request"
    sent_messages = captured_payloads[0]["messages"]
    assert sent_messages[1]["role"] == "assistant"
    assert "browser_open" in sent_messages[1]["content"][0]["text"]
    assert sent_messages[2]["role"] == "user"
    assert "<observation>" in sent_messages[2]["content"][0]["text"]
