"""Standalone demo of the virtual cursor overlay.
Runs the overlay and fires synthetic click + type events so you can see
exactly what the user sees when the agent drives the desktop.
"""
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.widget.virtual_cursor import VirtualCursorOverlay


def main():
    app = QApplication(sys.argv)
    overlay = VirtualCursorOverlay()
    overlay.show()

    # Simulated agent activity: cursor drifts around the screen along
    # smooth bezier curves, clicks, types, and shows action labels.
    events = [
        ("action", None, None, "Looking at the screen"),
        ("click",  400, 300, "Clicking"),
        ("action", None, None, "Reading the screen"),
        ("click",  800, 500, "Clicking File menu"),
        ("type",   820, 530, "Hello world"),
        ("action", 900, 600, "Scrolling"),
        ("click",  1100, 200, "Double-clicking"),
        ("click",  600, 700, "Clicking"),
        ("type",   620, 720, "agent at work"),
        ("click",  300, 400, "Clicking"),
    ]

    state = {"i": 0}

    def fire_next():
        if state["i"] >= len(events):
            QTimer.singleShot(2000, app.quit)
            return
        ev = events[state["i"]]
        state["i"] += 1
        kind = ev[0]
        if kind == "click":
            label = ev[3] if len(ev) > 3 else "Clicking"
            overlay.show_click(ev[1], ev[2], label=label)
        elif kind == "type":
            overlay.show_type(ev[1], ev[2], ev[3])
        elif kind == "action":
            label = ev[3]
            overlay.show_action(label, ev[1], ev[2])
        QTimer.singleShot(1000, fire_next)

    QTimer.singleShot(500, fire_next)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
