"""Hybrid resolver: UIA -> OCR pixel (local, no model) -> (agent escalates to
vision). Plus uia_type post-action verification. These exercise the fallback
wiring with the OCR + UIA layers mocked, so they run without a real desktop."""
from pathlib import Path

import app.tools as tools_mod
from app.tools import ToolExecutor


def _ex(tmp_path):
    return ToolExecutor(Path(tmp_path), home_dir=Path(tmp_path))


def test_uia_click_falls_back_to_ocr_on_uia_miss(monkeypatch, tmp_path):
    import app.widget.desktop_features as df

    # UIA finds nothing...
    monkeypatch.setattr(df, "invoke_ui_element",
                        lambda q, a: {"ok": False, "error": "no UIA control matched"})
    # ...but OCR locates the on-screen text.
    monkeypatch.setattr(df, "ocr_find_in_app",
                        lambda q, a: {"ok": True, "x": 329, "y": 216,
                                      "matched": "Edit", "score": 100})
    monkeypatch.setattr(df, "app_window_rect",
                        lambda a: {"left": 0, "top": 0, "width": 800, "height": 600})

    clicked = {}
    fake_pyautogui = type("PG", (), {"click": staticmethod(
        lambda x, y: clicked.update(x=x, y=y))})
    monkeypatch.setitem(__import__("sys").modules, "pyautogui", fake_pyautogui)

    res = _ex(tmp_path).uia_click("Edit", "Notepad")
    assert res.ok is True
    assert clicked == {"x": 329, "y": 216}
    assert res.data["overlay"]["control_layer"] == "OCR fallback"
    assert res.data["method"] == "ocr_pixel"


def test_uia_click_reports_miss_when_uia_and_ocr_both_fail(monkeypatch, tmp_path):
    import app.widget.desktop_features as df

    monkeypatch.setattr(df, "invoke_ui_element",
                        lambda q, a: {"ok": False, "error": "no UIA control matched"})
    monkeypatch.setattr(df, "ocr_find_in_app",
                        lambda q, a: {"ok": False, "error": "no OCR text matched"})
    monkeypatch.setattr(df, "app_window_rect",
                        lambda a: {"left": 0, "top": 0, "width": 0, "height": 0})

    res = _ex(tmp_path).uia_click("Reply", "Chrome")
    assert res.ok is False
    # the agent will escalate to the vision model from here
    assert res.data["overlay"]["control_layer"] == "UIA miss"


def test_uia_find_falls_back_to_ocr_on_uia_miss(monkeypatch, tmp_path):
    import app.widget.desktop_features as df

    # No accessible control in the tree...
    monkeypatch.setattr(df, "find_ui_elements",
                        lambda q, a, n: {"ok": False, "error": "no UIA control matched"})
    # ...but the text is visible on screen.
    monkeypatch.setattr(df, "ocr_find_in_app",
                        lambda q, a: {"ok": True, "x": 227, "y": 421,
                                      "matched": "Find", "score": 100})
    monkeypatch.setattr(df, "app_window_rect",
                        lambda a: {"left": 0, "top": 0, "width": 800, "height": 600})

    res = _ex(tmp_path).uia_find("Find", "Notepad")
    assert res.ok is True
    assert res.data["layer"] == "ocr"
    assert res.data["overlay"]["control_layer"] == "OCR fallback"
    assert res.data["items"][0]["x"] == 227 and res.data["items"][0]["y"] == 421
    assert "OCR matches" in res.output


def test_uia_find_reports_miss_when_uia_and_ocr_both_fail(monkeypatch, tmp_path):
    import app.widget.desktop_features as df

    monkeypatch.setattr(df, "find_ui_elements",
                        lambda q, a, n: {"ok": False, "error": "no UIA control matched"})
    monkeypatch.setattr(df, "ocr_find_in_app",
                        lambda q, a: {"ok": False, "error": "no OCR text matched"})
    monkeypatch.setattr(df, "app_window_rect",
                        lambda a: {"left": 0, "top": 0, "width": 0, "height": 0})

    res = _ex(tmp_path).uia_find("Ghost", "Chrome")
    assert res.ok is False
    assert res.data["overlay"]["control_layer"] == "UIA miss"


def test_ocr_norm_matches_through_punctuation_and_accelerators(monkeypatch):
    import app.widget.desktop_features as df

    # OCR sees menu labels with an accelerator '&' and trailing ellipsis; the
    # agent's query is the bare word. Normalisation should still match exactly.
    screen = [
        {"text": "&File", "x": 20, "y": 10},
        {"text": "Find...", "x": 80, "y": 10},
        {"text": "Edit,", "x": 140, "y": 10},
    ]
    monkeypatch.setattr(df, "app_window_rect",
                        lambda a: {"left": 0, "top": 0, "width": 400, "height": 300})
    monkeypatch.setattr(df, "win_ocr_words", lambda l, t, w, h: screen)

    hit = df.ocr_find_in_app("Find", "Notepad")
    assert hit["ok"] is True
    assert (hit["x"], hit["y"]) == (80, 10)
    assert hit["score"] == 100  # exact after normalising the trailing "..."

    assert df.ocr_find_in_app("File", "Notepad")["score"] == 100  # '&' stripped
    assert df.ocr_find_in_app("Edit", "Notepad")["score"] == 100  # ',' stripped


def test_ocr_phrase_match_requires_word_boundary(monkeypatch):
    import app.widget.desktop_features as df

    # "view" must NOT match the substring inside "teview codebase" — that kind of
    # cross-word hit would send a fallback click to the wrong place.
    screen = [
        {"text": "teview", "x": 50, "y": 40},
        {"text": "codebase", "x": 120, "y": 40},
    ]
    monkeypatch.setattr(df, "app_window_rect",
                        lambda a: {"left": 0, "top": 0, "width": 400, "height": 300})
    monkeypatch.setattr(df, "win_ocr_words", lambda l, t, w, h: screen)

    assert df.ocr_find_in_app("view", "Notepad")["ok"] is False
    # but a real whole-word phrase hit still matches
    screen2 = [{"text": "Review", "x": 50, "y": 40}, {"text": "codebase", "x": 120, "y": 40}]
    monkeypatch.setattr(df, "win_ocr_words", lambda l, t, w, h: screen2)
    assert df.ocr_find_in_app("review codebase", "Notepad")["score"] >= 100


def test_uia_type_reports_verification(monkeypatch, tmp_path):
    import app.widget.desktop_features as df

    monkeypatch.setattr(df, "type_into_ui_element",
                        lambda q, t, a, c, s: {"ok": True, "method": "paste",
                                               "target": "Text editor", "rect": {}})
    monkeypatch.setattr(df, "app_window_rect",
                        lambda a: {"left": 0, "top": 0, "width": 800, "height": 600})

    class _VP:
        Value = "hello world"

    class _Ctrl:
        def GetValuePattern(self):
            return _VP()

    monkeypatch.setattr(df, "_find_uia_control", lambda q, a: (_Ctrl(), {}))

    res = _ex(tmp_path).uia_type("Text editor", "hello world", "Notepad")
    assert res.ok is True
    assert res.data["verified"] is True
    assert "verified" in res.output
