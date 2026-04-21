"""Process-wide HistoryDB singleton for the MCP server.

Opening a fresh SQLite handle per tool call wastes file descriptors
and risks write-lock contention when an agent fires several tools
in quick succession; one shared connection is enough.
"""
from __future__ import annotations

import logging

from core.history import HistoryDB

log = logging.getLogger("fartrun.mcp")

_DB_INSTANCE: HistoryDB | None = None


def db() -> HistoryDB:
    """Return the cached HistoryDB, creating it on first call."""
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        _DB_INSTANCE = HistoryDB()
        _DB_INSTANCE.init()
    return _DB_INSTANCE


def reset_db_for_tests() -> None:
    """Drop the cached singleton — tests use this between runs so each
    test gets a HistoryDB pointing at its own tmp_path."""
    global _DB_INSTANCE
    if _DB_INSTANCE is not None:
        try:
            _DB_INSTANCE.close()
        except Exception as e:
            log.warning("close cached HistoryDB: %s", e)
    _DB_INSTANCE = None
