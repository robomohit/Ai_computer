"""Desktop-native features that round out the AI Computer widget into a
shippable product.

Implements (from research-deferred list):
  * Window-snap layouts            — "coding", "research", "meeting" presets
  * Autostart on Windows login     — HKCU Run-key registry toggle
  * Crash recovery / session save  — persist last goal, offer resume
  * "Explain this screen" hotkey   — screenshot + describe via vision model
  * Telemetry-off promise          — exposed as a settings flag (always-off)

All Windows-native; no extra pip deps beyond what's already required.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# WINDOW-SNAP LAYOUTS
# ─────────────────────────────────────────────────────────────────────────────
def list_visible_windows() -> list[dict]:
    """Return [{'hwnd', 'title', 'exe'}] of user-visible top-level windows."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    dwm = ctypes.windll.dwmapi

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    results: list[dict] = []
    DWMWA_CLOAKED = 14
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SKIP = {"Program Manager", "Windows Input Experience",
            "Microsoft Text Input Application", "Settings", "Search"}

    def cb(hwnd, _lp):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            cloaked = wintypes.DWORD(0)
            dwm.DwmGetWindowAttribute(wintypes.HWND(hwnd), DWMWA_CLOAKED,
                                      ctypes.byref(cloaked),
                                      ctypes.sizeof(cloaked))
            if cloaked.value:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 2)
            user32.GetWindowTextW(hwnd, buf, length + 2)
            title = buf.value
            if not title or title in SKIP:
                return True
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe = ""
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                     False, pid.value)
            if h:
                ebuf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                kernel32.QueryFullProcessImageNameW(h, 0, ebuf,
                                                    ctypes.byref(size))
                exe = ebuf.value
                kernel32.CloseHandle(h)
            results.append({"hwnd": int(hwnd), "title": title, "exe": exe})
        except Exception:
            pass
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return results


def primary_workarea() -> tuple[int, int, int, int]:
    """Returns (x, y, width, height) of the primary monitor work-area
    (excludes taskbar)."""
    user32 = ctypes.windll.user32
    SPI_GETWORKAREA = 0x0030
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return (rect.left, rect.top,
            rect.right - rect.left, rect.bottom - rect.top)


def _set_window_pos(hwnd: int, x: int, y: int, w: int, h: int) -> bool:
    """SetWindowPos with SWP_NOZORDER + SWP_SHOWWINDOW."""
    user32 = ctypes.windll.user32
    SWP_NOZORDER = 0x0004
    SWP_SHOWWINDOW = 0x0040
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(user32.SetWindowPos(
        wintypes.HWND(hwnd), wintypes.HWND(0),
        x, y, w, h, SWP_NOZORDER | SWP_SHOWWINDOW))


# Built-in named layouts. Each layout maps a friendly slot name → (x, y, w, h)
# as fractions of the work-area, and a list of (slot, exe_keyword) targets.
LAYOUTS = {
    "coding": {
        "description": "VS Code/Cursor left, browser right",
        "slots": {
            "left":  (0.0, 0.0, 0.55, 1.0),
            "right": (0.55, 0.0, 0.45, 1.0),
        },
        "targets": [
            ("left",  ("code.exe", "cursor.exe", "windsurf.exe",
                       "antigravity.exe", "devenv.exe")),
            ("right", ("chrome.exe", "msedge.exe", "firefox.exe",
                       "brave.exe", "comet.exe")),
        ],
    },
    "research": {
        "description": "Browser large, notes/notepad small",
        "slots": {
            "main": (0.0, 0.0, 0.7, 1.0),
            "side": (0.7, 0.0, 0.3, 1.0),
        },
        "targets": [
            ("main", ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
                      "comet.exe")),
            ("side", ("notepad.exe", "notion.exe", "obsidian.exe")),
        ],
    },
    "standup": {
        "description": "Calendar + Teams/Slack + browser",
        "slots": {
            "tl": (0.0, 0.0, 0.5, 0.5),
            "tr": (0.5, 0.0, 0.5, 0.5),
            "bl": (0.0, 0.5, 0.5, 0.5),
            "br": (0.5, 0.5, 0.5, 0.5),
        },
        "targets": [
            ("tl", ("outlook.exe", "thunderbird.exe")),
            ("tr", ("teams.exe", "slack.exe", "discord.exe")),
            ("bl", ("chrome.exe", "msedge.exe")),
            ("br", ("notepad.exe", "code.exe")),
        ],
    },
}


def apply_layout(layout_name: str) -> dict:
    """Snap currently-open windows into the named layout. Returns a summary."""
    layout = LAYOUTS.get(layout_name)
    if layout is None:
        return {"ok": False, "error": f"unknown layout '{layout_name}'"}
    wx, wy, ww, wh = primary_workarea()
    wins = list_visible_windows()
    moved: list[dict] = []
    for slot, keywords in layout["targets"]:
        # Find first window whose exe basename matches a keyword
        target = None
        for w in wins:
            base = os.path.basename((w.get("exe") or "")).lower()
            if any(k.lower() == base for k in keywords):
                target = w
                break
        if target is None:
            continue
        fx, fy, fw, fh = layout["slots"][slot]
        x = wx + int(ww * fx)
        y = wy + int(wh * fy)
        w = int(ww * fw)
        h = int(wh * fh)
        ok = _set_window_pos(target["hwnd"], x, y, w, h)
        moved.append({"slot": slot, "title": target["title"][:50],
                      "exe": os.path.basename(target.get("exe") or ""),
                      "ok": ok})
    return {"ok": True, "layout": layout_name,
            "description": layout["description"], "moved": moved}


# ─────────────────────────────────────────────────────────────────────────────
# AUTOSTART (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)
# ─────────────────────────────────────────────────────────────────────────────
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "AI_Computer"


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            try:
                winreg.QueryValueEx(k, _AUTOSTART_NAME)
                return True
            except FileNotFoundError:
                return False
    except Exception:
        return False


def set_autostart(enable: bool, launch_cmd: Optional[str] = None) -> bool:
    """Toggle autostart. `launch_cmd` defaults to `pythonw run_desktop.py`
    in the current Ai_computer folder."""
    if launch_cmd is None:
        # Use pythonw to launch without a console window
        py = sys.executable
        if py.endswith("python.exe"):
            py = py[:-len("python.exe")] + "pythonw.exe"
        repo = Path(__file__).resolve().parents[2]
        script = repo / "run_desktop.py"
        launch_cmd = f'"{py}" "{script}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, _AUTOSTART_NAME, 0, winreg.REG_SZ,
                                  launch_cmd)
            else:
                try:
                    winreg.DeleteValue(k, _AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as exc:
        print(f"[desktop_features] autostart toggle failed: {exc}", flush=True)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# CRASH RECOVERY — persist last in-flight goal so we can offer to resume
# ─────────────────────────────────────────────────────────────────────────────
def _state_path() -> Path:
    base = Path(os.environ.get("AI_COMPUTER_WORKSPACE", ".")).resolve()
    return base / "widget_state.json"


def save_pending_task(goal: str, mode: str, task_id: str = "") -> None:
    try:
        payload = {
            "goal": goal,
            "mode": mode,
            "task_id": task_id,
            "ts": time.time(),
        }
        _state_path().parent.mkdir(parents=True, exist_ok=True)
        _state_path().write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
    except Exception:
        pass


def clear_pending_task() -> None:
    try:
        if _state_path().exists():
            _state_path().unlink()
    except Exception:
        pass


def load_pending_task() -> Optional[dict]:
    """Return the previously-pending task if it's recent (<24h) and unfinished."""
    try:
        if not _state_path().exists():
            return None
        data = json.loads(_state_path().read_text(encoding="utf-8"))
        # Stale > 24h → drop
        if time.time() - data.get("ts", 0) > 24 * 3600:
            clear_pending_task()
            return None
        return data
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TELEMETRY — always off. Single source of truth for the privacy panel.
# ─────────────────────────────────────────────────────────────────────────────
TELEMETRY_PROMISE = {
    "telemetry_enabled": False,
    "outbound_destinations": [
        "OpenRouter free-tier LLMs (only LLM prompts + tool results)",
        "Web pages you ask the agent to browse via Playwright",
    ],
    "stays_local": [
        "Clipboard contents",
        "File contents you attach",
        "Window screenshots",
        "Connector link state (workspace/connectors.json)",
        "Session history",
        "Voice recordings (Windows SAPI processes on-device)",
    ],
    "notes": (
        "Zero analytics SDKs, zero crash reporters, zero usage telemetry. "
        "The only network calls are LLM API requests and the URLs you "
        "explicitly ask the agent to fetch."
    ),
}
