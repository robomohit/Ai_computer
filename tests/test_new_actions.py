import asyncio
import json
import pytest
import types
import time

from app.models import Action, ActionType
from app.safety import SafetyManager
from app.text_editor import TextEditorTool
from app.tools import ToolExecutor
import app.tools as tools_module

@pytest.mark.asyncio
async def test_new_actions(monkeypatch, workspace):
    calls = {}
    pg = types.SimpleNamespace(
        moveTo=lambda *a, **k: calls.setdefault("moveTo", []).append((a, k)),
        scroll=lambda v: calls.setdefault("scroll", []).append(v),
        doubleClick=lambda *a, **k: calls.setdefault("doubleClick", []).append((a, k)),
        click=lambda *a, **k: calls.setdefault("click", []).append((a, k)),
        dragTo=lambda *a, **k: calls.setdefault("dragTo", []).append((a, k)),
        hotkey=lambda *a: calls.setdefault("hotkey", []).append(a),
        keyDown=lambda k: calls.setdefault("keyDown", []).append(k),
        keyUp=lambda k: calls.setdefault("keyUp", []).append(k),
        position=lambda: (5, 7),
        write=lambda x, **kw: calls.setdefault("write", []).append(x),
        size=lambda: (1920, 1080),
        easeInOutQuad=lambda n: n,  # tween function used by moveTo/dragTo
    )
    monkeypatch.setitem(__import__("sys").modules, "pyautogui", pg)
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))

    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))
    
    assert (await t.run_action(Action(id="1", type=ActionType.scroll, args={"amount": 3, "x": 1, "y": 2}))).ok
    assert calls["scroll"][-1] == 3
    
    assert (await t.run_action(Action(id="2", type=ActionType.key_combo, args={"keys": "ctrl+shift+t"}))).ok
    assert calls["hotkey"][-1] == ("ctrl", "shift", "t")
    
    assert (await t.run_action(Action(id="3", type=ActionType.wait_action, args={"seconds": 2}))).ok
    assert slept[-1] == 2
    
    assert (await t.run_action(Action(id="4", type=ActionType.double_click, args={"x": 1, "y": 1}))).ok
    assert (await t.run_action(Action(id="5", type=ActionType.right_click, args={"x": 1, "y": 1}))).ok
    assert (await t.run_action(Action(id="6", type=ActionType.middle_click, args={"x": 1, "y": 1}))).ok
    
    assert (await t.run_action(Action(id="7", type=ActionType.mouse_move, args={"x": 1, "y": 1}))).ok
    assert (await t.run_action(Action(id="8", type=ActionType.left_click_drag, args={"x": 2, "y": 2}))).ok
    assert (await t.run_action(Action(id="9", type=ActionType.hold_key, args={"key": "a", "duration": 1}))).ok
    
    out = await t.run_action(Action(id="10", type=ActionType.cursor_position, args={}))
    assert out.data == {"x": 5, "y": 7}

    bash_out = await t.run_action(Action(id="11", type=ActionType.bash, args={"command": "cd ."}))
    assert bash_out.ok

    (workspace / "subdir").mkdir()
    (workspace / "subdir" / "marker.txt").write_text("ok", encoding="utf-8")
    bash_cd_run = await t.run_action(
        Action(id="11b", type=ActionType.bash, args={"command": "cd subdir && python -c \"from pathlib import Path; print(Path('marker.txt').read_text())\""})
    )
    assert bash_cd_run.ok
    assert "ok" in bash_cd_run.output

    bash_mkdir = await t.run_action(Action(id="11c", type=ActionType.bash, args={"command": "mkdir -p nested/project"}))
    assert bash_mkdir.ok
    assert (workspace / "nested" / "project").is_dir()

    run_mkdir = await t.run_action(Action(id="11d", type=ActionType.run_command, args={"command": "mkdir -p command_project"}))
    assert run_mkdir.ok
    assert (workspace / "command_project").is_dir()

    text_create_out = await t.run_action(
        Action(
            id="12",
            type=ActionType.text_editor,
            args={"command": "create", "path": "alias.txt", "file_text": "hello"},
        )
    )
    assert text_create_out.ok

    text_view_out = await t.run_action(
        Action(
            id="13",
            type=ActionType.text_editor,
            args={"command": "view", "path": "alias.txt"},
        )
    )
    assert "hello" in text_view_out.output

    computer_out = await t.run_action(
        Action(
            id="14",
            type=ActionType.computer,
            args={"action": "key", "keys": "ctrl+l"},
        )
    )
    assert computer_out.ok
    assert calls["hotkey"][-1] == ("ctrl", "l")

def test_safety_key_combo():
    s = SafetyManager()
    dec = s.evaluate(Action(id="1", type=ActionType.key_combo, args={"keys": "ctrl+alt+del"}))
    assert dec.danger.value == "high"


def test_file_glob_stays_inside_workspace(workspace):
    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("print('ok')", encoding="utf-8")

    result = t.file_glob("**/*.py")
    assert result.ok
    assert "src" in result.output

    with pytest.raises(Exception):
        t.file_glob("../**/*")
    with pytest.raises(Exception):
        t.file_glob(str((workspace.parent / "*.py").resolve()))


def test_safety_bash():
    s = SafetyManager()
    dec = s.evaluate(Action(id="2", type=ActionType.bash, args={"command": "echo hi"}))
    assert dec.danger.value == "high"


def test_run_tests_rewrites_bare_pytest(workspace, monkeypatch):
    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return types.SimpleNamespace(returncode=0, stdout="1 passed in 0.01s", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    result = t.run_tests(command="pytest smoke_tests -q")

    assert result.ok
    assert seen["command"] == "python -m pytest smoke_tests -q"


def test_hung_window_check_tolerates_missing_pywin32_helper(monkeypatch):
    fake_user32 = types.SimpleNamespace(IsHungAppWindow=lambda hwnd: 0)
    fake_windll = types.SimpleNamespace(user32=fake_user32)
    fake_ctypes = types.SimpleNamespace(windll=fake_windll)
    fake_win32gui = types.SimpleNamespace()

    monkeypatch.setattr(tools_module, "ctypes", fake_ctypes)
    monkeypatch.setattr(tools_module, "win32gui", fake_win32gui)

    assert tools_module._is_hung_app_window(1234) is False


@pytest.mark.asyncio
async def test_run_action_offloads_blocking_tool(workspace, monkeypatch):
    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))

    def slow_run_command(command: str):
        time.sleep(0.2)
        return types.SimpleNamespace(ok=True, output="done", base64_image=None, data=None)

    monkeypatch.setattr(t, "run_command", slow_run_command)

    started = time.monotonic()
    task = asyncio.create_task(t.run_action(Action(id="slow", type=ActionType.run_command, args={"command": "echo hi"})))
    await asyncio.sleep(0.05)
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    result = await task
    assert result.ok


@pytest.mark.asyncio
async def test_run_action_streams_run_command(workspace, monkeypatch):
    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))
    seen = []

    async def fake_stream(command, on_chunk=None):
        if on_chunk:
            await on_chunk("hello\n")
            await on_chunk("world\n")
        return types.SimpleNamespace(ok=True, output="hello\nworld\n", base64_image=None, data=None)

    monkeypatch.setattr(t, "run_command_streaming", fake_stream)

    async def on_stream(chunk):
        seen.append(chunk)

    result = await t.run_action(
        Action(id="stream", type=ActionType.run_command, args={"command": "echo hi"}),
        on_stream=on_stream,
    )
    assert result.ok
    assert seen == ["hello\n", "world\n"]
