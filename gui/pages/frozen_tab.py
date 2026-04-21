"""Frozen Files tab — lock files AI must not touch.

Shown inside SavePointsPage alongside Code and Environment tabs.

Locking is one-click: picking a file writes it into ``CLAUDE.md`` AND
installs the PreToolUse hook automatically if it isn't already. There is
no separate "enable hard block" toggle — hard block is the default.

Smart lock: user describes in plain text what works ("login, payments"),
Haiku finds the matching files, user confirms, files get locked.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QFileDialog, QInputDialog, QLineEdit, QMessageBox,
)

from i18n import get_string as _t
from core.history import HistoryDB
from core import frozen_manager as fm
from gui.win95 import (
    BUTTON_STYLE, FIELD_STYLE, FONT_MONO, HINT_STRIP_STYLE,
    PRIMARY_BUTTON_STYLE, SHADOW, SUNKEN_FRAME_STYLE, TITLE_DARK,
)

log = logging.getLogger(__name__)


class SmartLockThread(QThread):
    """Background thread: scan project files + ask Haiku which ones match."""

    results_ready = pyqtSignal(list)  # list of relative paths
    error = pyqtSignal(str)

    def __init__(self, project_dir: str, description: str, config: dict):
        super().__init__()
        self._project_dir = project_dir
        self._description = description
        self._config = config

    def run(self):
        try:
            root = Path(self._project_dir)
            # Collect source files (skip venvs, node_modules, .git, __pycache__)
            skip_dirs = {
                ".git", "node_modules", "__pycache__", ".venv", "venv",
                "env", ".env", "dist", "build", ".next", ".nuxt",
                "migrations", "__tests__",
            }
            source_exts = {
                ".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".svelte",
                ".go", ".rs", ".java", ".rb", ".php", ".swift", ".kt",
            }
            files: list[str] = []
            for p in root.rglob("*"):
                if any(part in skip_dirs for part in p.parts):
                    continue
                if p.is_file() and p.suffix in source_exts:
                    try:
                        rel = str(p.relative_to(root))
                    except ValueError:
                        continue
                    files.append(rel)
                if len(files) >= 500:
                    break

            if not files:
                self.error.emit(_t("frozen_smart_no_files"))
                return

            # Build prompt for Haiku
            file_list = "\n".join(files)
            prompt = (
                f"Project files:\n{file_list}\n\n"
                f"The user says these features work and should NOT be touched:\n"
                f"\"{self._description}\"\n\n"
                f"Return ONLY the file paths (one per line, no numbering, no "
                f"explanation) that are most likely related to what the user "
                f"described. Include files that handle the described "
                f"functionality: routes, views, controllers, services, "
                f"components, models, middleware. Be thorough but precise — "
                f"only files directly related to the description."
            )

            from core.haiku_client import HaikuClient
            client = HaikuClient(config=self._config)
            client._min_interval = 0
            if not client.is_available():
                self.error.emit(_t("frozen_smart_no_key"))
                return

            response = client.ask(prompt, max_tokens=1000)
            if not response:
                self.error.emit(_t("frozen_smart_no_files"))
                return

            # Parse response — each line is a file path
            file_set = set(files)
            matched = []
            for line in response.strip().split("\n"):
                line = line.strip().lstrip("- ").strip("`")
                if line in file_set:
                    matched.append(line)

            if matched:
                self.results_ready.emit(matched)
            else:
                self.error.emit(_t("frozen_smart_no_files"))

        except Exception as e:
            log.error("Smart lock error: %s", e)
            self.error.emit(str(e))


class FrozenTab(QWidget):
    """List of frozen files + add/unlock. Hook installs automatically."""

    def __init__(self):
        super().__init__()
        self._project_dir: str | None = None
        self._config: dict | None = None
        self._db: HistoryDB | None = None
        self._smart_thread: SmartLockThread | None = None
        self._build_ui()
        self._refresh()

    def _get_db(self) -> HistoryDB:
        if self._db is None:
            self._db = HistoryDB()
            self._db.init()
        return self._db

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Hint
        hint = QLabel(_t("frozen_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STRIP_STYLE)
        layout.addWidget(hint)

        # Smart lock — text description + find button
        smart_row = QHBoxLayout()
        self._smart_input = QLineEdit()
        self._smart_input.setPlaceholderText(_t("frozen_smart_placeholder"))
        self._smart_input.setStyleSheet(FIELD_STYLE)
        self._smart_input.returnPressed.connect(self._on_smart_lock)
        smart_row.addWidget(self._smart_input)

        self._btn_smart = QPushButton(_t("frozen_smart_btn"))
        self._btn_smart.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._btn_smart.clicked.connect(self._on_smart_lock)
        smart_row.addWidget(self._btn_smart)
        layout.addLayout(smart_row)

        self._smart_status = QLabel("")
        self._smart_status.setStyleSheet("color: #555; font-size: 11px; padding: 2px;")
        self._smart_status.hide()
        layout.addWidget(self._smart_status)

        # Action — single Add button. Hook is auto-installed on first add.
        actions = QHBoxLayout()
        self._btn_add = QPushButton(_t("frozen_add_btn"))
        self._btn_add.setStyleSheet(BUTTON_STYLE)
        self._btn_add.clicked.connect(self._on_add)
        actions.addWidget(self._btn_add)
        actions.addStretch()
        layout.addLayout(actions)

        # Scroll of frozen files
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 2px inset {SHADOW}; background: white; }}"
        )
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._content)
        layout.addWidget(scroll, 1)

    # --- Public API ---

    def set_project_dir(self, path: str) -> None:
        self._project_dir = path
        self._btn_add.setEnabled(True)
        self._refresh()

    def set_config(self, config: dict) -> None:
        self._config = config

    # --- Smart lock ---

    def _on_smart_lock(self) -> None:
        text = self._smart_input.text().strip()
        if not text or not self._project_dir:
            return
        if not self._config:
            self._smart_status.setText(_t("frozen_smart_no_key"))
            self._smart_status.show()
            return

        self._btn_smart.setEnabled(False)
        self._smart_status.setText(_t("frozen_smart_searching"))
        self._smart_status.show()

        self._smart_thread = SmartLockThread(
            self._project_dir, text, self._config,
        )
        self._smart_thread.results_ready.connect(self._on_smart_results)
        self._smart_thread.error.connect(self._on_smart_error)
        self._smart_thread.finished.connect(
            lambda: self._btn_smart.setEnabled(True)
        )
        self._smart_thread.start()

    def _on_smart_results(self, paths: list[str]) -> None:
        self._smart_status.hide()
        # Show file list and ask confirmation
        file_list = "\n".join(f"  {p}" for p in paths)
        msg = _t("frozen_smart_confirm").format(len(paths)) + "\n\n" + file_list
        reply = QMessageBox.question(
            self, _t("frozen_add_title"), msg,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        description = self._smart_input.text().strip()
        for p in paths:
            self._get_db().add_frozen_file(self._project_dir, p, description)

        self._sync_claude_md()
        self._ensure_hook_installed()
        self._smart_input.clear()
        self._smart_status.setText(_t("frozen_smart_done").format(len(paths)))
        self._smart_status.show()
        self._refresh()

    def _on_smart_error(self, msg: str) -> None:
        self._smart_status.setText(msg)
        self._smart_status.show()

    # --- Actions ---

    def _on_add(self) -> None:
        if not self._project_dir:
            return
        fp, _ok = QFileDialog.getOpenFileName(
            self, _t("frozen_add_title"), self._project_dir,
        )
        if not fp:
            return
        # Store as relative to project when possible
        try:
            rel = str(Path(fp).resolve().relative_to(
                Path(self._project_dir).resolve()))
        except ValueError:
            rel = fp

        note, _ = QInputDialog.getText(
            self, _t("frozen_add_title"), _t("frozen_note_prompt"),
        )
        self._get_db().add_frozen_file(self._project_dir, rel, note or "")
        self._sync_claude_md()
        self._ensure_hook_installed()
        self._refresh()

    def _on_unlock(self, path: str) -> None:
        if not self._project_dir:
            return
        self._get_db().remove_frozen_file(self._project_dir, path)
        self._sync_claude_md()
        self._refresh()

    def _ensure_hook_installed(self) -> None:
        """Install the PreToolUse hook on first lock; silent if already there."""
        if fm.is_hook_installed():
            return
        if not fm.install_hook():
            QMessageBox.warning(
                self, "Claude Code",
                _t("frozen_hook_install_failed"),
            )

    # --- Rendering ---

    def _sync_claude_md(self) -> None:
        if not self._project_dir:
            return
        frozen = self._get_db().get_frozen_files(self._project_dir)
        fm.sync_claude_md(self._project_dir, [f["path"] for f in frozen])

    def _refresh(self) -> None:
        self._render_list()

    def _render_list(self) -> None:
        # Clear
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._project_dir:
            self._show_placeholder(_t("snap_no_dir"))
            return

        frozen = self._get_db().get_frozen_files(self._project_dir)
        if not frozen:
            self._show_placeholder(_t("frozen_empty"))
            return

        for f in frozen:
            self._content_layout.addWidget(self._make_row(f))

    def _show_placeholder(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color: #808080; font-size: 13px; padding: 40px;"
        )
        self._content_layout.addWidget(lbl)

    def _make_row(self, f: dict) -> QFrame:
        """Render one frozen file row.

        Lock icon is fixed-width, baseline-aligned; path + note sit in a
        stacked layout that's top-aligned so the icon lines up with the
        path, not the middle of the row.
        """
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { border-bottom: 1px solid #e0e0e0; padding: 6px; }"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(6, 4, 6, 4)
        row.setAlignment(Qt.AlignTop)

        lock_icon = QLabel("\U0001F512")  # 🔒
        lock_icon.setFixedWidth(22)
        lock_icon.setStyleSheet("font-size: 14px; padding-top: 1px;")
        lock_icon.setAlignment(Qt.AlignTop)
        row.addWidget(lock_icon)

        info_widget = QWidget()
        info = QVBoxLayout(info_widget)
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        info.setAlignment(Qt.AlignTop)

        path_lbl = QLabel(f["path"])
        path_lbl.setStyleSheet(
            f"font-family: {FONT_MONO}; font-weight: bold; color: {TITLE_DARK};"
        )
        path_lbl.setWordWrap(True)
        info.addWidget(path_lbl)

        if f.get("note"):
            note_lbl = QLabel(f["note"])
            note_lbl.setStyleSheet("color: #555; font-size: 11px;")
            note_lbl.setWordWrap(True)
            info.addWidget(note_lbl)

        row.addWidget(info_widget, 1)

        btn_unlock = QPushButton(_t("frozen_unlock"))
        btn_unlock.setStyleSheet(BUTTON_STYLE)
        btn_unlock.clicked.connect(lambda _, p=f["path"]: self._on_unlock(p))
        row.addWidget(btn_unlock, 0, Qt.AlignTop)

        return frame
