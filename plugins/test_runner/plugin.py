"""TestRunnerPlugin — fulfils the Plugin(ABC) contract.

Storage lives in HistoryDB (sync sqlite3, see Task 18 in the original
reliability spec for the threading work). The aiosqlite `db` argument
the contract passes is intentionally ignored — `migrate()` is a no-op
and `collect()` is too, because runs are event-triggered (button /
save-point / watch), not collected on a timer.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.history import HistoryDB
from core.plugin import Alert, Plugin

if TYPE_CHECKING:
    from textual.widget import Widget  # legacy contract type


class TestRunnerPlugin(Plugin):
    name = "Tests"
    icon = "🧪"

    def __init__(self, config: dict):
        raw = config.get("plugins", {}).get("test_runner", {})
        self._config = raw if isinstance(raw, dict) else {}
        self._project_dir: str | None = self._config.get("project_dir")

    async def migrate(self, db) -> None:  # noqa: ARG002
        """No-op. test_runs table is owned by HistoryDB."""

    async def collect(self, db) -> None:  # noqa: ARG002
        """No-op. Runs fire on user/save-point/watch triggers, not on a timer."""

    async def get_alerts(self, db) -> list[Alert]:  # noqa: ARG002
        if not self._project_dir:
            return []
        history = self._history_db()
        last = await asyncio.to_thread(history.get_last_test_run, self._project_dir)
        if last is None:
            return []
        if last["timed_out"] or (last.get("failed") or 0) > 0:
            failed = last.get("failed") or 0
            total = (last.get("passed") or 0) + failed + (last.get("errors") or 0)
            title = "Tests timed out" if last["timed_out"] else f"Tests failing ({failed}/{total})"
            return [Alert(
                source="tests", severity="warning",
                title=title,
                message=f"Last run finished with exit code {last['exit_code']}",
            )]
        return []

    def render(self):
        # PyQt5 GUI doesn't use this. Placeholder fulfils the Plugin contract.
        from PyQt5.QtWidgets import QWidget
        return QWidget()

    def _history_db(self) -> HistoryDB:
        # Indirection so tests can patch it.
        return HistoryDB()
