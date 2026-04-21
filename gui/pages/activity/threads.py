"""Background QThreads owned by ``ActivityPage`` — Haiku helpers."""
from __future__ import annotations

import logging

from PyQt5.QtCore import QThread, pyqtSignal

from core.models import ActivityEntry

log = logging.getLogger(__name__)


class HaikuPromptsThread(QThread):
    """Ask Haiku to summarize a list of user prompts ('what were you trying to do?')."""

    result_ready = pyqtSignal(str)

    def __init__(self, prompts_text: str, config: dict,
                 on_api_error=None, parent=None):
        super().__init__(parent)
        self._text = prompts_text
        # Shallow copy so a Settings save mid-run doesn't pull config
        # out from under us.
        self._config = dict(config or {})
        self._on_api_error = on_api_error

    def run(self):
        try:
            from core.haiku_client import HaikuClient
            client = HaikuClient(config=self._config,
                                 on_api_error=self._on_api_error)
            if not client.is_available():
                self.result_ready.emit("")
                return

            lang = self._config.get("general", {}).get("language", "en")
            if lang == "ua":
                prompt = (
                    "Ти — помічник для vibe-кодерів. Нижче — список промптів, "
                    "що юзер писав у Claude Code (від старих до нових). "
                    "Напиши 2-4 речення простою мовою: з чого почали, "
                    "що робили далі, де застрягли. Без технічного жаргону. "
                    "Не використовуй markdown (ні # заголовків, ні **жирного**).\n\n"
                    + self._text
                )
            else:
                prompt = (
                    "You're a helper for vibe coders. Below is a list of "
                    "prompts the developer sent to Claude Code (oldest to "
                    "newest). Write 2-4 plain-English sentences: what they "
                    "started with, what they did next, where they got stuck. "
                    "No tech jargon. No markdown (no # headers, no **bold**).\n\n"
                    + self._text
                )
            summary = client.ask(prompt, max_tokens=300)
            self.result_ready.emit(summary or "")
        except Exception as e:
            log.error("HaikuPromptsThread error: %s", e, exc_info=True)
            self.result_ready.emit("")


class HaikuContextThread(QThread):
    """Background thread — asks Haiku for 'where you stopped' summary.

    Single ``ask()`` call only — previous version issued two in a row and
    the second was blocked by the 5s rate gate in ``HaikuClient``, causing
    ``haiku_summary`` to always be empty. The short summary for the DB is
    derived from the first sentence of the context.
    """

    result_ready = pyqtSignal(str, str)  # (haiku_context, haiku_summary)

    def __init__(self, entry: ActivityEntry, config: dict, on_api_error=None, parent=None):
        super().__init__(parent)
        self._entry = entry
        self._config = dict(config or {})
        self._on_api_error = on_api_error

    def run(self):
        try:
            from core.haiku_client import HaikuClient
            client = HaikuClient(config=self._config, on_api_error=self._on_api_error)
            if not client.is_available():
                self.result_ready.emit("", "")
                return

            lang = self._config.get("general", {}).get("language", "en")

            # Build activity summary text for Haiku
            parts = []
            if self._entry.files:
                file_list = ", ".join(f.path for f in self._entry.files[:10])
                parts.append(f"Files changed: {file_list}")
            if self._entry.commits:
                parts.append(f"Recent commits: {'; '.join(self._entry.commits[:3])}")
            if self._entry.docker_changes:
                docker_list = ", ".join(
                    f"{d.name} ({d.status})" for d in self._entry.docker_changes
                )
                parts.append(f"Docker: {docker_list}")
            if self._entry.port_changes:
                port_list = ", ".join(
                    f":{p.port} {p.status}" for p in self._entry.port_changes
                )
                parts.append(f"Ports: {port_list}")

            if not parts:
                self.result_ready.emit("", "")
                return

            activity_text = "\n".join(parts)

            # Single ask() — rate gate would block a second call.
            # Ask in the user's language; demand plain text (no markdown).
            prompt = (
                f"You are a friendly dev assistant who explains things in plain "
                f"human language — no jargon, no formality, like talking to a "
                f"colleague over coffee. Based on recent project activity, "
                f"write in {lang} a short summary (3-5 sentences max):\n"
                f"- What was DONE (completed work)\n"
                f"- What is NOT FINISHED yet (in progress or needs attention)\n"
                f"Be specific about file names and changes. No markdown "
                f"(no '#' headers, no '**bold**'), plain text only.\n\n"
                f"Activity:\n{activity_text}"
            )
            haiku_context = client.ask(prompt, max_tokens=250) or ""

            # Derive DB summary: first sentence of the context.
            haiku_summary = haiku_context.split(".")[0].strip() if haiku_context else ""
            if haiku_summary and not haiku_summary.endswith("."):
                haiku_summary += "."

            self.result_ready.emit(haiku_context, haiku_summary)

        except Exception as e:
            log.error("HaikuContextThread error: %s", e, exc_info=True)
            self.result_ready.emit("", "")
