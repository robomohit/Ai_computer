"""Hold the cursor overlay open for ~12s firing a click every 1.5s
so a screenshot tool can grab a frame."""
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.widget.virtual_cursor import VirtualCursorOverlay


def main():
    app = QApplication(sys.argv)
    overlay = VirtualCursorOverlay()
    overlay.show()
    state = {"i": 0}
    coords = [(450, 350), (800, 500), (1100, 250), (600, 700), (400, 600)]
    def fire():
        x, y = coords[state["i"] % len(coords)]
        state["i"] += 1
        overlay.show_click(x, y)
        QTimer.singleShot(1500, fire)
    QTimer.singleShot(300, fire)
    QTimer.singleShot(12000, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
