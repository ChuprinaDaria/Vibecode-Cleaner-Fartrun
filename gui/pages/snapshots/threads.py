"""Background QThreads owned by ``SnapshotsPage`` — Haiku diff explainer."""
from __future__ import annotations

import logging

from PyQt5.QtCore import QThread, pyqtSignal

from i18n import get_language

log = logging.getLogger(__name__)


class HaikuSnapshotThread(QThread):
    """Ask Haiku to explain what changed between two snapshots."""

    result_ready = pyqtSignal(str)

    def __init__(self, diff_text: str, config: dict, on_api_error=None, parent=None):
        super().__init__(parent)
        self._diff_text = diff_text
        self._config = dict(config or {})
        self._on_api_error = on_api_error

    def run(self):
        try:
            api_key = self._config.get("haiku", {}).get("api_key", "")
            if not api_key:
                self.result_ready.emit("")
                return
            from core.haiku_client import HaikuClient
            client = HaikuClient(api_key, on_api_error=self._on_api_error)
            lang = get_language()
            if lang == "ua":
                prompt = (
                    "Ти — помічник для vibe-кодерів. Поясни що змінилось у середовищі "
                    "між двома знімками. Говори простою мовою, одним-двома реченнями, "
                    "без технічного жаргону. Ось різниця:\n\n" + self._diff_text
                )
            else:
                prompt = (
                    "You're an assistant for vibe coders. Explain in plain English what "
                    "changed in the environment between two snapshots. Keep it to 1-2 sentences, "
                    "no tech jargon. Here's the diff:\n\n" + self._diff_text
                )
            explanation = client.ask(prompt, max_tokens=300)
            self.result_ready.emit(explanation or "")
        except Exception as e:
            log.debug("HaikuSnapshotThread error: %s", e)
            self.result_ready.emit("")
