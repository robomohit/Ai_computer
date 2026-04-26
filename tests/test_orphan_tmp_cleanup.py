"""Regression tests for orphan task-store .tmp cleanup at startup."""
from __future__ import annotations

import importlib
import os


def test_orphan_tmp_files_removed_on_startup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_API_KEY", "token123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "abc123.json").write_text('{"id":"abc123","status":"done"}', encoding="utf-8")

    orphan = tasks_dir / ".abc123.json.deadbeef.tmp"
    orphan.write_text("partial", encoding="utf-8")
    assert orphan.exists()

    import app.main as m

    importlib.reload(m)

    assert not orphan.exists(), "Orphan tmp file should have been cleaned up at startup"
    assert (tasks_dir / "abc123.json").exists(), "Real task files must NOT be removed"
