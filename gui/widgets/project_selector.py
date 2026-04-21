"""Shared project selector widget — QComboBox + Browse button.

Used across Activity, Health, and Snapshots tabs so the user
doesn't have to select the project directory on every tab separately.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QFileDialog,
)
from PyQt5.QtCore import pyqtSignal

from core.history import HistoryDB
from core.project_detector import detect_projects, get_last_project, save_last_project
from gui.win95 import BUTTON_STYLE, FIELD_STYLE, FONT_UI, GRAY, SHADOW

log = logging.getLogger(__name__)


class ProjectSelector(QWidget):
    """Dropdown of detected Claude projects + Browse button.

    Emits `project_changed(path: str)` whenever the active project changes.
    """

    project_changed = pyqtSignal(str)

    def __init__(
        self,
        db: HistoryDB,
        claude_dir: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._claude_dir = claude_dir

        # Wrap the selector in a Win95 raised panel so it reads as the
        # "current context" strip above the content stack.
        self.setStyleSheet(
            f"ProjectSelector {{ background: {GRAY}; "
            f"border-bottom: 2px groove {SHADOW}; font-family: {FONT_UI}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        from i18n import get_string as _t
        self._t = _t

        self._label = QLabel(_t("project_label"))
        self._label.setStyleSheet(f"font-family: {FONT_UI}; font-weight: bold;")
        layout.addWidget(self._label)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(320)
        self._combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._combo.setStyleSheet(FIELD_STYLE)
        layout.addWidget(self._combo, stretch=1)

        self._browse_btn = QPushButton(_t("project_browse"))
        self._browse_btn.setStyleSheet(BUTTON_STYLE)
        self._browse_btn.clicked.connect(self._on_browse)
        layout.addWidget(self._browse_btn)

        # Populate from detected projects
        self._populate()

        # Wire combo change signal after population to avoid spurious emits
        self._combo.currentIndexChanged.connect(self._on_index_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def current_project(self) -> str | None:
        """Return currently selected project path, or None if nothing selected."""
        path = self._combo.currentData()
        if path and path != "__none__":
            return path
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        """Fill combo with detected projects and restore last selection."""
        self._combo.blockSignals(True)
        self._combo.clear()

        from i18n import get_string as _t
        self._combo.addItem(_t("project_none"), "__none__")

        projects = []
        if self._claude_dir:
            try:
                projects = detect_projects(self._claude_dir)
            except Exception as e:
                log.warning("detect_projects failed: %s", e)

        for p in projects:
            display = f"{p['name']}  ({p['path']})"
            self._combo.addItem(display, p["path"])

        # Restore last used project
        last = None
        try:
            last = get_last_project(self._db)
        except Exception as e:
            log.warning("get_last_project failed: %s", e)

        if last:
            idx = self._combo.findData(last)
            if idx == -1:
                # Not in list (manually browsed path) — add it
                self._combo.addItem(last, last)
                idx = self._combo.count() - 1
            self._combo.setCurrentIndex(idx)
        else:
            self._combo.setCurrentIndex(0)

        self._combo.blockSignals(False)

    def _on_index_changed(self, index: int) -> None:
        path = self._combo.itemData(index)
        if not path or path == "__none__":
            return
        try:
            save_last_project(self._db, path)
        except Exception as e:
            log.warning("save_last_project failed: %s", e)
        self.project_changed.emit(path)

    def _on_browse(self) -> None:
        from i18n import get_string as _t
        directory = QFileDialog.getExistingDirectory(
            self,
            _t("project_browse"),
            str(Path.home()),
        )
        if not directory:
            return

        # Add to combo if not already present
        idx = self._combo.findData(directory)
        if idx == -1:
            self._combo.addItem(directory, directory)
            idx = self._combo.count() - 1

        self._combo.setCurrentIndex(idx)
        # _on_index_changed fires automatically from signal
