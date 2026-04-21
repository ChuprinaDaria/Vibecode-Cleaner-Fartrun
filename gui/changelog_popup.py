"""Changelog popup — shown when Claude Code version changes."""
from __future__ import annotations
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from i18n import get_string as _t, get_language

class HaikuChangelogThread(QThread):
    done = pyqtSignal(str)
    def __init__(self, old_version: str, new_version: str, config: dict, parent=None):
        super().__init__(parent)
        self._old = old_version
        self._new = new_version
        self._config = dict(config or {})
    def run(self):
        try:
            from core.haiku_client import HaikuClient
            haiku = HaikuClient(config=self._config)
            if not haiku.is_available():
                self.done.emit("")
                return
            lang = get_language()
            lang_name = "Ukrainian" if lang == "ua" else "English"
            result = haiku.ask(
                f"Claude Code updated from version {self._old} to {self._new}. "
                f"Briefly explain what might be new and whether anything could break "
                f"in existing projects. 3-5 sentences, simple words. Respond in {lang_name}.",
                max_tokens=300
            ) or ""
            self.done.emit(result)
        except Exception:
            self.done.emit("")

class ChangelogPopup(QDialog):
    """Win95-style popup for Claude Code updates with Haiku explanation."""
    def __init__(self, old_version: str, new_version: str, changelog_url: str,
                 config: dict | None = None, parent=None):
        super().__init__(parent)
        self._changelog_url = changelog_url
        self._dismissed = False
        self._config = config or {}
        self.setWindowTitle(_t("changelog_title"))
        self.setMinimumSize(420, 220)
        self.setStyleSheet("QDialog { background: #c0c0c0; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(_t("changelog_title"))
        title.setFont(QFont("MS Sans Serif", 14, QFont.Bold))
        title.setStyleSheet("color: #000080;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(8)

        version_lbl = QLabel(f"{old_version}  \u2192  {new_version}")
        version_lbl.setFont(QFont("MS Sans Serif", 16, QFont.Bold))
        version_lbl.setAlignment(Qt.AlignCenter)
        version_lbl.setStyleSheet("color: #000000;")
        layout.addWidget(version_lbl)
        layout.addSpacing(8)

        self._haiku_label = QLabel(_t("changelog_message"))
        self._haiku_label.setWordWrap(True)
        self._haiku_label.setAlignment(Qt.AlignLeft)
        self._haiku_label.setStyleSheet(
            "color: #333; font-size: 12px; padding: 8px; background: #f8f8ff; border: 1px solid #d0d0d0;"
        )
        layout.addWidget(self._haiku_label)
        layout.addSpacing(12)

        buttons = QHBoxLayout()
        btn_got_it = QPushButton(_t("changelog_got_it"))
        btn_got_it.setStyleSheet(
            "QPushButton { background: #000080; color: white; padding: 6px 20px; "
            "border: 2px outset #4040c0; font-weight: bold; }"
            "QPushButton:pressed { border: 2px inset #000080; }"
        )
        btn_got_it.clicked.connect(self._on_got_it)
        buttons.addWidget(btn_got_it)

        btn_changelog = QPushButton(_t("changelog_show_full"))
        btn_changelog.setStyleSheet(
            "QPushButton { padding: 6px 20px; border: 2px outset #dfdfdf; }"
            "QPushButton:pressed { border: 2px inset #808080; }"
        )
        btn_changelog.clicked.connect(self._on_show_changelog)
        buttons.addWidget(btn_changelog)
        layout.addLayout(buttons)

        self._haiku_thread = HaikuChangelogThread(old_version, new_version, self._config)
        self._haiku_thread.done.connect(self._on_haiku_done)
        self._haiku_thread.start()

    def _on_haiku_done(self, text: str) -> None:
        if text:
            self._haiku_label.setText(text)
            self.setMinimumSize(420, 300)
            self.adjustSize()

    def _on_got_it(self) -> None:
        self._dismissed = True
        self.accept()

    def _on_show_changelog(self) -> None:
        from core.platform import get_platform
        get_platform().open_url(self._changelog_url)

    @property
    def was_dismissed(self) -> bool:
        return self._dismissed
