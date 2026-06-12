"""Offscreen Qt tests for the capsule's dynamic widget cards.

Pins two user-facing regressions:
1. The adaptive palette flip — item rows/buttons hardcoded dark-mode colors,
   so light-mode cards rendered near-white text on a near-white surface.
2. The delete confirm — the icon-only trash button fired /api/capsule/delete
   for every listed file on a single (possibly stray) click.
"""
from __future__ import annotations

import os

import pytest

PySide6 = pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

import app.widget.capsule_widgets as cw  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


SPEC = {
    "title": "Clutter",
    "items": [{"name": "video.mp4", "detail": "80 MB"}],
    "buttons": [
        {"label": "Open", "style": "secondary", "action": "open_folder", "payload": {}},
        {"label": "", "style": "danger", "icon": "trash",
         "action": "/api/capsule/delete", "payload": {"file_paths": ["x"]}},
    ],
    "text": "**bold** body",
}


def _styles(widget, cls):
    return [c.styleSheet() for c in widget.findChildren(cls)]


def test_light_palette_flips_item_and_button_chrome(qapp):
    cw.set_card_palette(True)
    try:
        card = cw.DynamicWidget(SPEC)
        labels = _styles(card, QLabel)
        btns = _styles(card, QPushButton)
        assert any(cw.ITEM_TEXT in s for s in labels), "light item text missing"
        assert not any("#E2E4E8" in s for s in labels), "dark item text leaked into light mode"
        assert any(cw.BTN_TEXT in s for s in btns), "light button text missing"
    finally:
        cw.set_card_palette(False)
    card_dark = cw.DynamicWidget(SPEC)
    assert any("#E2E4E8" in s for s in _styles(card_dark, QLabel)), "dark palette did not restore"


def test_delete_action_requires_second_tap(qapp, monkeypatch):
    launched = []
    monkeypatch.setattr(
        cw.threading, "Thread",
        lambda *a, **k: launched.append(k) or type("T", (), {"start": lambda self: None})(),
    )
    card = cw.DynamicWidget(SPEC)
    btn = QPushButton("  x")

    # First tap arms — must NOT launch the HTTP worker.
    card._execute_action("/api/capsule/delete", {"file_paths": ["x"]}, btn)
    assert launched == []
    assert getattr(btn, "_confirm_armed", False) is True
    assert "confirm" in btn.text().lower()

    # Second tap fires.
    card._execute_action("/api/capsule/delete", {"file_paths": ["x"]}, btn)
    assert len(launched) == 1

    # Non-destructive endpoints fire immediately, no arming.
    launched.clear()
    btn2 = QPushButton("Organize")
    card._execute_action("/api/capsule/organize", {"folder_path": "x"}, btn2)
    assert len(launched) == 1
