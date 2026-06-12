from __future__ import annotations

from app.adaptive_windows import (
    FailureClass,
    analyze_windows_failure,
    format_recovery_plan,
    remember_resolver_outcome,
    resolver_ids,
)
from app.tools import ToolExecutor


def test_adaptive_windows_classifies_missing_app():
    analysis = analyze_windows_failure(
        action="uia_click",
        query="Send",
        app="Discord",
        output="no UIA control matched 'Send' - no window titled like 'Discord' is open",
    )

    assert analysis.failure_class == FailureClass.app_not_found
    assert analysis.resolvers[0].id == "wait_for_window"
    assert analysis.resolvers[0].args["title"] == "Discord"


def test_adaptive_windows_promotes_exact_listed_control_name():
    analysis = analyze_windows_failure(
        action="uia_click",
        query="Fuor",
        app="Calculator",
        output=(
            "no UIA control matched 'Fuor'. Did you mean: 'Four'? "
            "Controls actually in this window (use these EXACT names): "
            "'Equals', 'Multiply by'."
        ),
    )

    assert analysis.failure_class == FailureClass.uia_no_match
    assert analysis.resolvers[0].id == "use_listed_control_name"
    assert analysis.resolvers[0].args["query"] == "Four"
    assert "Adaptive recovery plan" in format_recovery_plan(analysis)


def test_adaptive_windows_learned_resolver_is_promoted(monkeypatch, tmp_path):
    monkeypatch.setenv("ORYNN_WORKSPACE", str(tmp_path))

    remember_resolver_outcome(
        "CanvasApp",
        FailureClass.uia_no_match.value,
        "ocr_text_target",
        True,
        detail="Found Start by OCR",
    )
    analysis = analyze_windows_failure(
        action="uia_click",
        query="Start",
        app="CanvasApp",
        output="no UIA control matched 'Start'.",
    )

    assert resolver_ids(analysis.resolvers)[0] == "ocr_text_target"
    assert analysis.learned[0]["successes"] == 1


def test_tool_executor_uia_find_attaches_adaptive_plan(monkeypatch, workspace):
    import app.widget.desktop_features as desktop_features

    def fake_find_ui_elements(query, app, limit):
        return {
            "ok": False,
            "error": (
                "no UIA control matched 'Fuor'. Did you mean: 'Four'? "
                "Controls actually in this window (use these EXACT names): 'Equals'."
            ),
        }

    monkeypatch.setattr(desktop_features, "find_ui_elements", fake_find_ui_elements)
    monkeypatch.setattr(ToolExecutor, "_ocr_find_fallback", lambda self, query, app: None)
    monkeypatch.setattr(ToolExecutor, "_electron_unlock_hint", lambda self, app, data: "")
    monkeypatch.setattr(ToolExecutor, "_app_rect_payload", staticmethod(lambda app: None))

    result = ToolExecutor(workspace).uia_find("Fuor", "Calculator")

    assert result.ok is False
    assert "Adaptive recovery plan" in result.output
    assert result.data["adaptive"]["failure_class"] == FailureClass.uia_no_match.value
    assert result.data["adaptive"]["resolvers"][0]["id"] == "use_listed_control_name"
