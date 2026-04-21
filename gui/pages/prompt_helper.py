"""Prompt Helper — turn a vibe coder's one-liner into a real Claude prompt.

User types a loose description, we search their codebase, detect the
stack, pull frozen files, and synthesise a structured prompt via Haiku
(with a template fallback). Context7 MCP can be installed from here with
one click.
"""

from __future__ import annotations

import logging

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFrame, QMessageBox, QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from i18n import get_string as _t
from core.prompt_builder import build_prompt, PromptBuildResult
from core.history import HistoryDB
from core import context7_mcp as c7
from gui.win95 import (
    BUTTON_STYLE, ERROR, FIELD_STYLE, FONT_MONO, FONT_UI, HINT_STRIP_STYLE,
    PAGE_TITLE_STYLE, PRIMARY_BUTTON_STYLE, SHADOW, SUCCESS, TITLE_DARK,
)

log = logging.getLogger(__name__)


class _BuilderThread(QThread):
    result_ready = pyqtSignal(object)  # PromptBuildResult

    def __init__(self, user_text: str, project_dir: str,
                 frozen_paths: list[str], config: dict,
                 on_api_error=None, parent=None):
        super().__init__(parent)
        self._text = user_text
        self._dir = project_dir
        self._frozen = frozen_paths
        # Shallow copy: shield the running thread from config mutations
        # made by Settings while it works.
        self._config = dict(config or {})
        self._on_api_error = on_api_error

    def run(self):
        haiku = None
        try:
            from core.haiku_client import HaikuClient
            client = HaikuClient(config=self._config,
                                 on_api_error=self._on_api_error)
            if client.is_available():
                haiku = client
        except Exception as e:
            log.debug("HaikuClient unavailable: %s", e)

        try:
            result = build_prompt(
                user_text=self._text,
                project_dir=self._dir,
                frozen_paths=self._frozen,
                haiku_client=haiku,
            )
        except Exception as e:
            log.error("Prompt build error: %s", e)
            result = PromptBuildResult(
                final_prompt=f"(error: {e})", language="en",
            )
        self.result_ready.emit(result)


class PromptHelperPage(QWidget):
    def __init__(self):
        super().__init__()
        self._project_dir: str | None = None
        self._config: dict = {}
        self._db: HistoryDB | None = None
        self._thread: _BuilderThread | None = None
        self._haiku_error_callback = None
        self._build_ui()
        self._refresh_context7_status()

    # --- Public API ---

    def set_project_dir(self, path: str) -> None:
        self._project_dir = path
        self._btn_build.setEnabled(bool(path))

    def set_config(self, config: dict) -> None:
        self._config = config

    def set_haiku_error_callback(self, callback) -> None:
        self._haiku_error_callback = callback

    def hide_dir_picker(self) -> None:
        """Called by app.py — we don't have our own picker, just enable button."""
        pass

    # --- UI ---

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel(_t("ph_header"))
        title.setFont(QFont("Tahoma", 14, QFont.Bold))
        title.setStyleSheet(PAGE_TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(_t("ph_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STRIP_STYLE)
        layout.addWidget(hint)

        # Input
        self._input = QTextEdit()
        self._input.setPlaceholderText(_t("ph_input_placeholder"))
        self._input.setStyleSheet(FIELD_STYLE)
        self._input.setFixedHeight(80)
        layout.addWidget(self._input)

        # Context7 status
        self._c7_frame = QFrame()
        c7_layout = QHBoxLayout(self._c7_frame)
        c7_layout.setContentsMargins(6, 6, 6, 6)

        self._c7_status = QLabel("")
        self._c7_status.setWordWrap(True)
        self._c7_status.setStyleSheet(f"font-size: 11px; font-family: {FONT_UI};")
        c7_layout.addWidget(self._c7_status, 1)

        self._c7_btn = QPushButton(_t("ph_context7_install_btn"))
        self._c7_btn.setStyleSheet(BUTTON_STYLE)
        self._c7_btn.clicked.connect(self._on_install_context7)
        c7_layout.addWidget(self._c7_btn)
        layout.addWidget(self._c7_frame)

        # Action row
        action_row = QHBoxLayout()
        self._btn_build = QPushButton(_t("ph_build_btn"))
        self._btn_build.setStyleSheet(
            PRIMARY_BUTTON_STYLE.replace("padding: 6px 14px", "padding: 8px 20px")
        )
        self._btn_build.setEnabled(False)
        self._btn_build.clicked.connect(self._on_build)
        action_row.addWidget(self._btn_build)
        action_row.addStretch()
        layout.addLayout(action_row)

        # Status label
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"color: {SHADOW}; font-size: 11px; padding: 4px; font-family: {FONT_UI};"
        )
        layout.addWidget(self._status)

        # Output
        out_title = QLabel(_t("ph_output_title"))
        out_title.setStyleSheet(
            f"font-weight: bold; color: {TITLE_DARK}; padding-top: 8px; "
            f"font-family: {FONT_UI};"
        )
        layout.addWidget(out_title)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(
            f"QTextEdit {{ border: 2px inset {SHADOW}; padding: 6px; "
            f"background: white; font-family: {FONT_MONO}; font-size: 12px; }}"
        )
        layout.addWidget(self._output, 1)

        # Copy
        copy_row = QHBoxLayout()
        self._btn_copy = QPushButton(_t("ph_copy_btn"))
        self._btn_copy.clicked.connect(self._on_copy)
        self._btn_copy.setEnabled(False)
        copy_row.addWidget(self._btn_copy)
        copy_row.addStretch()
        layout.addLayout(copy_row)

    # --- Context7 ---

    def _refresh_context7_status(self) -> None:
        if c7.is_context7_installed():
            self._c7_status.setText(_t("ph_context7_installed"))
            self._c7_status.setStyleSheet(
                f"color: {SUCCESS}; font-size: 11px; font-weight: bold; "
                f"font-family: {FONT_UI};"
            )
            self._c7_btn.hide()
        else:
            self._c7_status.setText(_t("ph_context7_missing"))
            self._c7_status.setStyleSheet(
                f"color: #808000; font-size: 11px; font-family: {FONT_UI};"
            )
            self._c7_btn.show()

    def _on_install_context7(self) -> None:
        if not c7.npx_available():
            QMessageBox.warning(self, "npx", _t("ph_npx_missing"))
            # Continue anyway — user might install Node later
        if c7.install_context7():
            QMessageBox.information(self, "Context7", _t("ph_context7_done"))
        self._refresh_context7_status()

    # --- Build ---

    def _get_db(self) -> HistoryDB:
        if self._db is None:
            self._db = HistoryDB()
            self._db.init()
        return self._db

    def _on_build(self) -> None:
        # Defence in depth: button is disabled while running, but a
        # programmatic trigger or a queued click could still reach this.
        if self._thread is not None and self._thread.isRunning():
            return

        text = self._input.toPlainText().strip()
        if not text or not self._project_dir:
            return

        # Gather frozen paths from DB for this project
        try:
            frozen = [f["path"] for f in
                      self._get_db().get_frozen_files(self._project_dir)]
        except Exception as e:
            log.warning("frozen-files lookup failed for prompt build: %s", e)
            frozen = []

        self._status.setText(_t("ph_working"))
        self._btn_build.setEnabled(False)
        self._btn_copy.setEnabled(False)
        self._output.clear()

        self._thread = _BuilderThread(
            user_text=text,
            project_dir=self._project_dir,
            frozen_paths=frozen,
            config=self._config,
            on_api_error=self._haiku_error_callback,
            parent=self,
        )
        self._thread.result_ready.connect(self._on_result)
        self._thread.finished.connect(
            lambda: self._btn_build.setEnabled(True)
        )
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_result(self, result: PromptBuildResult) -> None:
        self._output.setPlainText(result.final_prompt)
        self._btn_copy.setEnabled(True)

        note = ""
        if not result.used_ai:
            note = f" {_t('ph_no_ai')}"
        self._status.setText(
            f"Found {len(result.matches)} code matches · "
            f"Stack: {len(result.stack)} libs · "
            f"Context7 libs: {len(result.context7_libs)}{note}"
        )

    def _on_copy(self) -> None:
        QApplication.clipboard().setText(self._output.toPlainText())
        base = self._status.text().split("  ✓")[0]
        self._status.setText(base + "  ✓ copied")
