"""Native Qt widgets for the floating capsule.

Pure QWidget implementations — NO QWebEngineView, no HTML, no Tailwind.
Every icon is SVG-rendered to QPixmap for crisp monochrome display.
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, QByteArray, QPropertyAnimation, QEasingCurve,
    QSize, Signal, QParallelAnimationGroup, QTimer, QPoint,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QSizePolicy, QGraphicsOpacityEffect,
)

# ── SVG icon library ─────────────────────────────────────────────────────────
# All icons are Lucide-style 24×24 viewBox, thin monochrome strokes.
_SVG_PATHS = {
    "sparkles": '<path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/>'
                '<path d="M18 14l1 3 3 1-3 1-1 3-1-3-3-1 3-1z"/>',
    "folder":   '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "monitor":  '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/>'
                '<line x1="12" y1="17" x2="12" y2="21"/>',
    "clipboard":'<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
                '<rect x="8" y="2" width="8" height="4" rx="1"/>',
    "link":     '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
                '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "zap":      '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10"/>',
    "broom":    '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a1 1 0 0 0 0-1.4l-1.6-1.6a1 1 0 0 0-1.4 0z"/>'
                '<path d="m12 8-7.6 7.6A2 2 0 0 0 4 17v3a1 1 0 0 0 1 1h3a2 2 0 0 0 1.4-.6L17 13"/>',
    "file-text":'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                '<polyline points="14 2 14 8 20 8"/>'
                '<line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "image":    '<rect x="3" y="3" width="18" height="18" rx="2"/>'
                '<circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
    "archive":  '<polyline points="4 8 4 21 20 21 20 8"/>'
                '<rect x="2" y="3" width="20" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>',
    "settings": '<circle cx="12" cy="12" r="1.5"/>'
                '<path d="M6.5 12H2"/><path d="M22 12h-4.5"/>'
                '<path d="M12 6.5V2"/><path d="M12 22v-4.5"/>',
    "file":     '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                '<polyline points="14 2 14 8 20 8"/>',
    "x":        '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "check":    '<polyline points="20 6 9 17 4 12"/>',
    "trash":    '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
                '<path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
}


def _render_icon(name: str, size: int = 18, color: str = "#B0B4BC",
                 stroke_w: float = 1.7) -> QPixmap:
    """Render a named SVG icon to a crisp QPixmap."""
    body = _SVG_PATHS.get(name, "")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke_w}" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return pm


def _icon_label(name: str, size: int = 16, color: str = "#B0B4BC") -> QLabel:
    """Create a QLabel displaying a monochrome SVG icon."""
    lbl = QLabel()
    lbl.setPixmap(_render_icon(name, size, color))
    lbl.setFixedSize(size + 4, size + 4)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("background:transparent;border:none;")
    return lbl


# ── Shared styles ────────────────────────────────────────────────────────────
ACCENT = "#5BE0D0"
_NO_BG = "background:transparent;border:none;"


# ── Base card ────────────────────────────────────────────────────────────────
class CapsuleCard(QWidget):
    """Base class for every widget that spawns inside the capsule."""
    dismissed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity_fx = QGraphicsOpacityEffect(self)
        self._opacity_fx.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_fx)
        # Subtle elevated layer — NOT a heavy bordered box
        self.setStyleSheet(
            "CapsuleCard{"
            "  background: rgba(255, 255, 255, 0.04);"
            "  border: 1px solid rgba(255, 255, 255, 0.07);"
            "  border-radius: 14px;"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def animate_in(self):
        self.setMaximumHeight(0)
        target = self.sizeHint().height() + 30

        fade = QPropertyAnimation(self._opacity_fx, b"opacity")
        fade.setDuration(400)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)

        expand = QPropertyAnimation(self, b"maximumHeight")
        expand.setDuration(480)
        expand.setStartValue(0)
        expand.setEndValue(target)
        expand.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(fade)
        self._anim_group.addAnimation(expand)
        self._anim_group.start()

    def animate_out(self):
        fade = QPropertyAnimation(self._opacity_fx, b"opacity")
        fade.setDuration(220)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.InCubic)
        fade.finished.connect(self._dismiss)
        self._fade_out = fade
        fade.start()

    def _dismiss(self):
        self.dismissed.emit()
        self.deleteLater()


# ── Capability bar ───────────────────────────────────────────────────────────
class CapabilityBar(QWidget):
    """Row of SVG capability icons below the search bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_NO_BG)
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()

        caps = [
            ("sparkles", "Auto detect"),
            ("folder", "Files"),
            ("monitor", "Screen"),
            ("clipboard", "Clipboard"),
            ("link", "Links"),
            ("zap", "Actions"),
        ]
        for icon_name, tip in caps:
            btn = QPushButton()
            btn.setIcon(QIcon(_render_icon(icon_name, 16, "#8A8F98")))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(tip)
            btn.setFixedSize(36, 32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{background:transparent;border:none;border-radius:8px;}"
                "QPushButton:hover{background:rgba(255,255,255,0.07);}"
            )
            layout.addWidget(btn)

        # thin vertical separator before "Actions"
        layout.addStretch()


# ── Dismiss button helper ────────────────────────────────────────────────────
def _make_dismiss_btn() -> QPushButton:
    btn = QPushButton()
    btn.setIcon(QIcon(_render_icon("x", 12, "#6B7280")))
    btn.setIconSize(QSize(12, 12))
    btn.setFixedSize(26, 26)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        "QPushButton{background:rgba(255,255,255,0.05);border:none;border-radius:13px;}"
        "QPushButton:hover{background:rgba(239,68,68,0.2);}"
    )
    return btn


def _thin_divider() -> QFrame:
    d = QFrame()
    d.setFixedHeight(1)
    d.setStyleSheet("background:rgba(255,255,255,0.06);border:none;")
    return d


# ── File row ─────────────────────────────────────────────────────────────────
_FILE_ICON_MAP = {
    "pdf": "file-text", "doc": "file-text", "txt": "file-text", "md": "file-text",
    "png": "image", "jpg": "image", "jpeg": "image", "svg": "image", "gif": "image",
    "zip": "archive", "tar": "archive", "gz": "archive", "rar": "archive",
    "exe": "settings", "msi": "settings", "bat": "settings",
}


def _guess_file_icon(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _FILE_ICON_MAP.get(ext, "file")


class _FileRow(QWidget):
    """One row inside the clutter-sweeper list — clean, borderless."""

    def __init__(self, name: str, size: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setStyleSheet(
            "QWidget{background:transparent;border:none;border-radius:8px;}"
            "QWidget:hover{background:rgba(255,255,255,0.04);}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 12, 0)
        row.setSpacing(10)

        icon_name = _guess_file_icon(name)
        ic = _icon_label(icon_name, 15, "#7A7F88")
        row.addWidget(ic)

        nm = QLabel(name)
        nm.setFont(QFont("Segoe UI Variable Text", 10))
        nm.setStyleSheet(f"color:#E2E4E8;{_NO_BG}")
        row.addWidget(nm, 1)

        sz = QLabel(size)
        sz.setFont(QFont("Segoe UI", 9))
        sz.setStyleSheet(f"color:#6B7280;{_NO_BG}")
        row.addWidget(sz)


# ── Clutter Sweeper widget ───────────────────────────────────────────────────
class ClutterSweeperWidget(CapsuleCard):
    """Shows files in a folder that can be organised / cleaned."""

    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        data = data or {}
        folder = data.get("folder", "Downloads")
        files = data.get("files", [
            {"name": "report_final_v3.pdf", "size": "4.2 MB"},
            {"name": "screenshot_2024.png", "size": "1.8 MB"},
            {"name": "node_modules.zip", "size": "142 MB"},
            {"name": "setup_installer.exe", "size": "28 MB"},
            {"name": "meeting_notes.txt", "size": "12 KB"},
        ])
        total = data.get("total_size", "176 MB")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(0)

        # ── header row ──
        hdr = QHBoxLayout()
        hdr.setSpacing(12)
        hdr.addWidget(_icon_label("broom", 20, ACCENT))

        col = QVBoxLayout()
        col.setSpacing(1)
        title = QLabel("Clutter Sweeper")
        title.setFont(QFont("Segoe UI Variable Display", 13, QFont.DemiBold))
        title.setStyleSheet(f"color:#FFFFFF;{_NO_BG}")
        col.addWidget(title)

        sub = QLabel(f"{len(files)} items in ~/{folder}  ·  {total} reclaimable")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color:#6B7280;{_NO_BG}")
        col.addWidget(sub)
        hdr.addLayout(col, 1)

        dismiss = _make_dismiss_btn()
        dismiss.clicked.connect(self.animate_out)
        hdr.addWidget(dismiss)
        lay.addLayout(hdr)

        # ── spacer ──
        lay.addSpacing(12)
        lay.addWidget(_thin_divider())
        lay.addSpacing(8)

        # ── file list ──
        for f in files[:6]:
            lay.addWidget(_FileRow(f["name"], f["size"]))

        if len(files) > 6:
            more = QLabel(f"+{len(files) - 6} more")
            more.setFont(QFont("Segoe UI", 9))
            more.setAlignment(Qt.AlignCenter)
            more.setStyleSheet(f"color:#4B5563;{_NO_BG}")
            more.setFixedHeight(24)
            lay.addWidget(more)

        # ── action buttons ──
        lay.addSpacing(12)
        btns = QHBoxLayout()
        btns.setSpacing(8)

        org = QPushButton("  Organize All")
        org.setIcon(QIcon(_render_icon("check", 14, "#0A1A16", 2.2)))
        org.setIconSize(QSize(14, 14))
        org.setCursor(Qt.PointingHandCursor)
        org.setFont(QFont("Segoe UI Variable Text", 10, QFont.DemiBold))
        org.setFixedHeight(38)
        org.setStyleSheet(
            f"QPushButton{{background:{ACCENT};color:#0A1A16;border:none;"
            f"border-radius:10px;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6FEDE0;}}"
        )
        btns.addWidget(org, 1)

        rev = QPushButton("  Review")
        rev.setIcon(QIcon(_render_icon("file-text", 14, "#B0B4BC")))
        rev.setIconSize(QSize(14, 14))
        rev.setCursor(Qt.PointingHandCursor)
        rev.setFont(QFont("Segoe UI Variable Text", 10))
        rev.setFixedHeight(38)
        rev.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.06);color:#D1D5DB;"
            "border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:0 18px;}"
            "QPushButton:hover{background:rgba(255,255,255,0.10);color:#FFFFFF;}"
        )
        btns.addWidget(rev, 1)

        del_btn = QPushButton()
        del_btn.setIcon(QIcon(_render_icon("trash", 15, "#6B7280")))
        del_btn.setIconSize(QSize(15, 15))
        del_btn.setFixedSize(38, 38)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);"
            "border-radius:10px;}"
            "QPushButton:hover{background:rgba(239,68,68,0.15);}"
        )
        btns.addWidget(del_btn)

        lay.addLayout(btns)


# ── Status Card ──────────────────────────────────────────────────────────────
class StatusCardWidget(CapsuleCard):
    """Simple text card — used for AI replies, status, errors."""

    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        data = data or {}
        text = data.get("text", "")
        icon = data.get("icon", "sparkles")
        card_title = data.get("title", "AI Computer")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        hdr.addWidget(_icon_label(icon, 18, ACCENT))
        t = QLabel(card_title)
        t.setFont(QFont("Segoe UI Variable Display", 12, QFont.DemiBold))
        t.setStyleSheet(f"color:#FFFFFF;{_NO_BG}")
        hdr.addWidget(t, 1)
        dismiss = _make_dismiss_btn()
        dismiss.clicked.connect(self.animate_out)
        hdr.addWidget(dismiss)
        lay.addLayout(hdr)

        if text:
            lay.addSpacing(10)
            lay.addWidget(_thin_divider())
            lay.addSpacing(10)
            body = QLabel(text)
            body.setWordWrap(True)
            body.setFont(QFont("Segoe UI", 10))
            body.setStyleSheet(f"color:#D1D5DB;{_NO_BG}line-height:1.5;")
            body.setMaximumHeight(300)
            lay.addWidget(body)


# ── Widget factory ───────────────────────────────────────────────────────────
WIDGET_REGISTRY: dict[str, type[CapsuleCard]] = {
    "clutter_sweeper": ClutterSweeperWidget,
    "status_card": StatusCardWidget,
}


def create_widget(widget_type: str, data: dict | None = None,
                  parent=None) -> CapsuleCard | None:
    cls = WIDGET_REGISTRY.get(widget_type)
    if cls is None:
        return None
    return cls(data=data, parent=parent)
