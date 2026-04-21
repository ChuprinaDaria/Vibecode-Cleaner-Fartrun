"""SDK Context popup — fetch docs for unknown packages, generate PROJECT_CONTEXT.md."""

from __future__ import annotations

import logging

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QFrame, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from i18n import get_string as _t

log = logging.getLogger(__name__)


class FetchThread(QThread):
    """Fetch URL in background."""
    done = pyqtSignal(object)  # ContextDoc or None

    def __init__(self, project_dir: str, url: str, parent=None):
        super().__init__(parent)
        self._dir = project_dir
        self._url = url

    def run(self):
        try:
            from core.context_fetcher import ContextFetcher
            fetcher = ContextFetcher(self._dir)
            result = fetcher.fetch_url(self._url)
            self.done.emit(result)
        except Exception as e:
            log.error("Fetch error: %s", e)
            self.done.emit(None)


class SDKContextPopup(QDialog):
    def __init__(self, project_dir: str, config: dict, parent=None):
        super().__init__(parent)
        self._project_dir = project_dir
        self._config = config
        self._fetch_thread: FetchThread | None = None
        self.setWindowTitle(_t("health_section_sdk_context"))
        self.setMinimumSize(600, 400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(_t("health_section_sdk_context"))
        title.setFont(QFont("MS Sans Serif", 14, QFont.Bold))
        title.setStyleSheet("color: #000080;")
        layout.addWidget(title)

        # Unknown packages
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 2px inset #808080; background: white; }")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setAlignment(Qt.AlignTop)

        try:
            from core.context_fetcher import ContextFetcher
            fetcher = ContextFetcher(self._project_dir)
            unknown = fetcher.detect_unknown_packages()
        except Exception:
            unknown = []

        if unknown:
            header = QLabel(_t("sdk_unknown_header"))
            header.setStyleSheet("font-weight: bold; color: #333; padding: 4px;")
            cl.addWidget(header)

            for pkg in unknown[:15]:
                row = QFrame()
                row.setStyleSheet("QFrame { border-bottom: 1px solid #e0e0e0; padding: 4px; }")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(4, 2, 4, 2)

                name_lbl = QLabel(f"! {pkg.name} {pkg.version}")
                name_lbl.setStyleSheet("color: #cc6600; font-weight: bold; font-family: monospace;")
                rl.addWidget(name_lbl)

                reg_lbl = QLabel(f"({pkg.registry})")
                reg_lbl.setStyleSheet("color: #808080;")
                rl.addWidget(reg_lbl)

                rl.addStretch()
                cl.addWidget(row)
        else:
            no_pkg = QLabel(_t("sdk_no_unknown"))
            no_pkg.setStyleSheet("color: #006600; padding: 8px;")
            cl.addWidget(no_pkg)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Manual URL fetch
        sep = QLabel("")
        sep.setStyleSheet("border-top: 1px solid #808080; margin: 4px 0;")
        layout.addWidget(sep)

        fetch_label = QLabel(_t("sdk_fetch_url_label"))
        fetch_label.setStyleSheet("font-weight: bold; padding: 4px 0;")
        layout.addWidget(fetch_label)

        url_row = QHBoxLayout()
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://docs.example.com/api")
        self._url_input.setStyleSheet("QLineEdit { border: 2px inset #808080; padding: 4px; background: white; }")
        url_row.addWidget(self._url_input)

        self._btn_fetch = QPushButton(_t("sdk_fetch_btn"))
        self._btn_fetch.setStyleSheet(
            "QPushButton { background: #000080; color: white; padding: 4px 12px; "
            "border: 2px outset #4040c0; font-weight: bold; }"
        )
        self._btn_fetch.clicked.connect(self._on_fetch)
        url_row.addWidget(self._btn_fetch)
        layout.addLayout(url_row)

        self._fetch_status = QLabel("")
        self._fetch_status.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addWidget(self._fetch_status)

        # Generate context button
        btn_row = QHBoxLayout()
        self._btn_generate = QPushButton(_t("sdk_generate_context"))
        self._btn_generate.setStyleSheet("QPushButton { padding: 6px 16px; font-weight: bold; }")
        self._btn_generate.clicked.connect(self._on_generate)
        btn_row.addWidget(self._btn_generate)

        gen_desc = QLabel(_t("sdk_generate_desc"))
        gen_desc.setStyleSheet("color: #808080; font-size: 11px;")
        gen_desc.setWordWrap(True)
        btn_row.addWidget(gen_desc)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        close_btn = QPushButton(_t("close"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _on_fetch(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url

        self._fetch_status.setText(_t("sdk_fetching"))
        self._fetch_status.setStyleSheet("color: #cc6600; font-size: 11px;")
        self._btn_fetch.setEnabled(False)

        self._fetch_thread = FetchThread(self._project_dir, url, self)
        self._fetch_thread.done.connect(self._on_fetch_done)
        self._fetch_thread.start()

    def _on_fetch_done(self, result) -> None:
        self._btn_fetch.setEnabled(True)
        if result:
            size_kb = result.size // 1024
            self._fetch_status.setText(
                f"Saved: {result.title} ({size_kb}KB) -> {result.path}"
            )
            self._fetch_status.setStyleSheet("color: #006600; font-size: 11px;")
        else:
            self._fetch_status.setText(_t("sdk_fetch_failed"))
            self._fetch_status.setStyleSheet("color: #cc0000; font-size: 11px;")

    def _on_generate(self) -> None:
        try:
            from core.context_fetcher import ContextFetcher
            fetcher = ContextFetcher(self._project_dir)
            path = fetcher.generate_context_file()
            QMessageBox.information(
                self, "Done",
                f"PROJECT_CONTEXT.md generated!\n\nPath: {path}\n\n"
                "Copy its content and paste into AI chat."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
