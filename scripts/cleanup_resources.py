#!/usr/bin/env python3
"""Clean common orphan processes and print a small RAM snapshot.

This is intentionally conservative: it targets development/test leftovers for
AI Computer only (server, pytest, and browser automation children) and avoids
matching the current Python process.
"""

from __future__ import annotations

import os
import signal
from pathlib import Path


TARGET_MARKERS = (
    "uvicorn",
    "pytest",
    "playwright",
    "chromium",
    "chrome",
    "msedge",
)


def _mem_available_kb() -> str:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return line.split()[1]
    except Exception:
        pass
    return "unknown"


def _cmdline(pid: str) -> str:
    try:
        return Path("/proc", pid, "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
    except Exception:
        return ""


def main() -> int:
    current_pid = os.getpid()
    killed: list[str] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == current_pid:
            continue
        cmd = _cmdline(proc.name).lower()
        if not cmd or not any(marker in cmd for marker in TARGET_MARKERS):
            continue
        try:
            os.kill(int(proc.name), signal.SIGTERM)
            killed.append(proc.name)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

    print(f"mem_available_kb={_mem_available_kb()}")
    print(f"killed_processes={len(killed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
