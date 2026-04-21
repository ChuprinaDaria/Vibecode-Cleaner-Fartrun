"""Permanent statusbar showing Claude version + API status."""

from __future__ import annotations

import random
from datetime import datetime

from PyQt5.QtWidgets import QStatusBar, QLabel
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QMouseEvent

from gui.win95 import ERROR, FONT_UI, GRAY, SHADOW
from i18n import get_string as _t

_STATUS_STYLES = {
    "none":     ("status_ok",       ""),
    "minor":    ("status_degraded", "background: #ffff00;"),
    "major":    ("status_down",     f"background: {ERROR}; color: white;"),
    "critical": ("status_down",     f"background: {ERROR}; color: white;"),
    "unknown":  ("status_unknown",  ""),
}

HOFF_OK = [
    "The Hoff is watching. All clear.",
    "All systems nominal. Hasselhoff approves.",
]
HOFF_DOWN = [
    "Even the Hoff can't fix this one. Wait.",
    "Don't hassle the API. It's down.",
]
HOFF_VERSION = [
    "The Hoff upgraded. New powers unlocked.",
]


class ClaudeStatusBar(QStatusBar):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Win95 statusbar chrome — gray with inset top border so it looks
        # like a sunken panel at the bottom of the window.
        self.setStyleSheet(
            f"QStatusBar {{ background: {GRAY}; "
            f"border-top: 2px groove {SHADOW}; font-family: {FONT_UI}; }}"
            f"QStatusBar QLabel {{ font-family: {FONT_UI}; font-size: 11px; }}"
        )
        self._prev_version: str | None = None
        self._version_label = QLabel("Claude: --")
        self._status_label = QLabel(_t("status_unknown"))
        self._time_label = QLabel("")

        for lbl in (self._version_label, self._status_label, self._time_label):
            lbl.setStyleSheet("padding: 0 8px;")

        self.addPermanentWidget(self._version_label)
        self.addPermanentWidget(self._status_label)
        self.addPermanentWidget(self._time_label)

    def update_status(self, indicator: str, version: str | None, timestamp: str) -> None:
        if version:
            self._version_label.setText(f"Claude {version}")
        else:
            self._version_label.setText(_t("status_claude_not_found"))

        key, bg_style = _STATUS_STYLES.get(indicator, _STATUS_STYLES["unknown"])
        self._status_label.setText(_t(key))
        if bg_style:
            self._status_label.setStyleSheet(f"padding: 0 8px; font-weight: bold; {bg_style}")
        else:
            self._status_label.setStyleSheet("padding: 0 8px;")

        try:
            checked = datetime.fromisoformat(timestamp)
            delta = datetime.now() - checked
            minutes = int(delta.total_seconds() / 60)
            if minutes < 1:
                ago = "just now"
            elif minutes < 60:
                ago = f"{minutes} min ago"
            else:
                ago = f"{minutes // 60}h ago"
            self._time_label.setText(_t("status_checked_ago").format(ago=ago))
        except (ValueError, TypeError):
            self._time_label.setText("")

        # Hasselhoff: version change or random 10%
        if version and self._prev_version and version != self._prev_version:
            self.showMessage(random.choice(HOFF_VERSION), 5000)
        elif random.random() < 0.10:
            if indicator == "none":
                self.showMessage(random.choice(HOFF_OK), 5000)
            elif indicator in ("major", "critical"):
                self.showMessage(random.choice(HOFF_DOWN), 5000)
        self._prev_version = version

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
