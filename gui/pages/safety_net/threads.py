"""Background QThreads owned by ``SafetyNetPage`` — Haiku hints."""
from __future__ import annotations

import logging

from PyQt5.QtCore import QThread, pyqtSignal

from core.git_educator import GitEducator

log = logging.getLogger(__name__)


class HaikuHintThread(QThread):
    """Ask Haiku for contextual hint in background."""
    result_ready = pyqtSignal(str)

    def __init__(self, action: str, context: dict, config: dict, parent=None):
        super().__init__(parent)
        self._action = action
        self._context = context
        self._config = dict(config or {})

    def run(self):
        try:
            from core.haiku_client import HaikuClient
            client = HaikuClient(config=self._config)
            if not client.is_available():
                self.result_ready.emit("")
                return
            lang = self._config.get("general", {}).get("language", "en")
            educator = GitEducator("", None, haiku=client)
            detail = educator._ask_haiku(self._action, self._context, lang)
            self.result_ready.emit(detail or "")
        except Exception as e:
            log.debug("HaikuHintThread error: %s", e)
            self.result_ready.emit("")
