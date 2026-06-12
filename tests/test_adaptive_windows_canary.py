from __future__ import annotations

import os
from pathlib import Path

import scripts.adaptive_windows_canary as canary


def test_summarize_results_reports_failed_canaries():
    results = [
        {"name": "notepad", "ok": True, "duration_s": 1.25},
        {"name": "calculator", "ok": False, "duration_s": 2.0},
    ]

    summary = canary.summarize_results(results)

    assert summary == {
        "ok": False,
        "total": 2,
        "passed": 1,
        "failed": 1,
        "failed_canaries": ["calculator"],
        "duration_s": 3.25,
    }


def test_run_canaries_marks_unknown_canary_failed(tmp_path):
    report = canary.run_canaries(["unknown"], tmp_path)

    assert report["summary"]["ok"] is False
    assert report["summary"]["failed_canaries"] == ["unknown"]
    assert report["results"][0]["failed_steps"] == ["unknown_canary"]


def test_run_canaries_uses_selected_runner(monkeypatch, tmp_path):
    calls = []
    seen_workspace_env = []

    def fake_notepad(workspace: Path):
        calls.append(workspace)
        seen_workspace_env.append(os.environ.get("ORYNN_WORKSPACE"))
        return {
            "name": "notepad",
            "ok": True,
            "duration_s": 0.5,
            "steps": [{"name": "map_notepad", "ok": True}],
            "failed_steps": [],
            "control_layers": ["Adaptive UIA map"],
            "affordance_maps": 1,
        }

    monkeypatch.setattr(canary, "run_notepad_canary", fake_notepad)
    monkeypatch.setenv("ORYNN_WORKSPACE", "original-workspace")

    report = canary.run_canaries(["notepad"], tmp_path)

    assert calls == [tmp_path]
    assert seen_workspace_env == [str(tmp_path)]
    assert os.environ.get("ORYNN_WORKSPACE") == "original-workspace"
    assert report["summary"]["ok"] is True
    assert report["results"][0]["affordance_maps"] == 1


def test_canary_result_flags_failed_steps():
    result = canary._canary_result(
        "demo",
        0.0,
        [
            {"name": "observe", "ok": True, "data": {"graph": {"controls": []}}},
            {"name": "act", "ok": False, "control_layer": "UIA miss"},
        ],
    )

    assert result["ok"] is False
    assert result["failed_steps"] == ["act"]
    assert result["affordance_maps"] == 1
