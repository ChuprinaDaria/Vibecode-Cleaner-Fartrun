"""Changelog Watcher — detect Claude Code version changes.

Runs `claude --version`, compares with last known version in SQLite,
shows notification if version changed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime

from core.history import HistoryDB

log = logging.getLogger(__name__)

CHANGELOG_URL = "https://docs.anthropic.com/en/docs/changelog"


def get_claude_version() -> str | None:
    """Get current Claude Code version via `claude --version`."""
    claude = shutil.which("claude")
    if not claude:
        return None
    try:
        result = subprocess.run(
            [claude, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode != 0:
            return None
        # Output might be "1.0.20" or "claude-code 1.0.20" etc.
        version = result.stdout.strip()
        # Extract version number if prefixed
        parts = version.split()
        for part in reversed(parts):
            if part and part[0].isdigit():
                return part
        return version if version else None
    except (subprocess.TimeoutExpired, OSError) as e:
        log.warning("claude --version failed: %s", e)
        return None


def _ensure_version_table(db: HistoryDB) -> None:
    """Create claude_versions table if not exists."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS claude_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            dismissed INTEGER DEFAULT 0
        )
    """)
    db.commit()


def get_last_known_version(db: HistoryDB) -> str | None:
    """Get the last known Claude Code version from DB."""
    _ensure_version_table(db)
    cursor = db.execute(
        "SELECT version FROM claude_versions ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    return row[0] if row else None


def save_version(db: HistoryDB, version: str) -> None:
    """Save a new detected version."""
    _ensure_version_table(db)
    db.execute(
        "INSERT INTO claude_versions (version, detected_at) VALUES (?, ?)",
        (version, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()


def dismiss_version(db: HistoryDB, version: str) -> None:
    """Mark version notification as dismissed."""
    _ensure_version_table(db)
    db.execute(
        "UPDATE claude_versions SET dismissed = 1 WHERE version = ?",
        (version,),
    )
    db.commit()


def is_dismissed(db: HistoryDB, version: str) -> bool:
    """Check if version notification was already dismissed."""
    _ensure_version_table(db)
    cursor = db.execute(
        "SELECT dismissed FROM claude_versions WHERE version = ? ORDER BY id DESC LIMIT 1",
        (version,),
    )
    row = cursor.fetchone()
    return bool(row and row[0])


def check_for_update(db: HistoryDB) -> dict | None:
    """Check if Claude Code was updated.

    Returns dict with update info or None if no update:
    {
        "old_version": "1.0.19",
        "new_version": "1.0.20",
        "changelog_url": "https://...",
    }
    """
    current = get_claude_version()
    if not current:
        return None

    last_known = get_last_known_version(db)

    if last_known is None:
        # First time — save and don't alert
        save_version(db, current)
        return None

    if current == last_known:
        return None

    # Version changed
    if is_dismissed(db, current):
        return None

    save_version(db, current)

    return {
        "old_version": last_known,
        "new_version": current,
        "changelog_url": CHANGELOG_URL,
    }
