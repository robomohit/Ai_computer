from __future__ import annotations

import json


def test_project_rules_and_workflow_expansion(tmp_path):
    from app.premium_features import discover_project_rules, expand_workflow_goal

    (tmp_path / "AGENTS.md").write_text("Use pytest and keep changes small.", encoding="utf-8")
    rules_dir = tmp_path / ".aicomputer" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "ui.md").write_text("UI controls must be accessible.", encoding="utf-8")
    workflows = tmp_path / ".aicomputer" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ship.md").write_text("Run tests, summarize risk, prepare rollback.", encoding="utf-8")

    rules = discover_project_rules(tmp_path)
    assert "AGENTS.md" in rules
    assert "Use pytest" in rules
    assert ".aicomputer" in rules

    expanded = expand_workflow_goal("/ship finish the feature", tmp_path)
    assert "finish the feature" in expanded
    assert "Workflow /ship" in expanded
    assert "rollback" in expanded


def test_preflight_plan_is_local_and_mode_aware():
    from app.premium_features import build_preflight_plan

    plan = build_preflight_plan("fix the failing tests", mode="coding", autonomy_level="careful")
    descriptions = [s["description"] for s in plan["sub_tasks"]]
    assert any("Inspect" in step for step in descriptions)
    assert any("Pause for approval" in step for step in descriptions)


def test_hooks_run_from_local_config(tmp_path):
    from app.premium_features import run_task_hooks

    (tmp_path / ".aicomputer").mkdir()
    (tmp_path / ".aicomputer" / "hooks.json").write_text(
        json.dumps({"task_done": [{"name": "echo", "command": "python -c \"print('hook ok')\""}]}),
        encoding="utf-8",
    )

    results = run_task_hooks(tmp_path, "task_done", {"task_id": "t1"})
    assert results[0]["name"] == "echo"
    assert results[0]["ok"] is True
    assert "hook ok" in results[0]["output"]


def test_detect_ollama_success(monkeypatch):
    from app import premium_features as pf

    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "llama3.2"}, {"name": "qwen2.5"}]}

    monkeypatch.setattr(pf.httpx, "get", lambda *a, **k: Resp())
    data = pf.detect_ollama("http://ollama.test")
    assert data["available"] is True
    assert data["models"] == ["llama3.2", "qwen2.5"]
