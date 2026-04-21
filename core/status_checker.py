"""StatusChecker — ping status.anthropic.com, parse indicator, log to SQLite."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.request import urlopen, Request

from core.history import HistoryDB
from core.changelog_watcher import get_claude_version

log = logging.getLogger(__name__)

STATUS_URL = "https://status.anthropic.com/api/v2/status.json"
HTTP_TIMEOUT = 5
VALID_INDICATORS = frozenset({"none", "minor", "major", "critical"})
VERSION_CHECK_INTERVAL = 300  # 5 minutes


@dataclass
class StatusResult:
    timestamp: str
    api_indicator: str
    api_description: str
    claude_version: str
    response_time_ms: int


def _ensure_status_table(db: HistoryDB) -> None:
    """Create api_status_log table if not exists."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS api_status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            api_indicator TEXT NOT NULL,
            api_description TEXT NOT NULL,
            claude_version TEXT NOT NULL,
            response_time_ms INTEGER NOT NULL
        )
    """)
    db.commit()


class StatusChecker:
    def __init__(self, db: HistoryDB) -> None:
        self._db = db
        self._last_version_check: float = 0.0
        self._cached_version: str = ""
        _ensure_status_table(db)

    def _get_version_throttled(self) -> str:
        """Get claude version, throttled to once per 5 minutes."""
        now = time.monotonic()
        if now - self._last_version_check >= VERSION_CHECK_INTERVAL:
            version = get_claude_version()
            self._cached_version = version or ""
            self._last_version_check = now
        return self._cached_version

    def check_now(self) -> StatusResult:
        """GET status.anthropic.com, parse, save to SQLite, prune old records."""
        ts = datetime.now().isoformat(timespec="seconds")
        version = self._get_version_throttled()

        indicator = "unknown"
        description = "Unknown"
        response_time_ms = 0

        try:
            start = time.monotonic()
            req = Request(STATUS_URL, headers={"User-Agent": "claude-monitor/1.0"})
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                body = resp.read()
            response_time_ms = int((time.monotonic() - start) * 1000)

            data = json.loads(body)
            raw_indicator = data["status"]["indicator"]
            raw_description = data["status"]["description"]

            if raw_indicator in VALID_INDICATORS:
                indicator = raw_indicator
                description = raw_description
            else:
                indicator = "unknown"
                description = f"Unexpected indicator: {raw_indicator}"

        except OSError as e:
            log.warning("Status check failed (network): %s", e)
            indicator = "unknown"
            description = f"Network error: {e}"
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("Status check failed (parse): %s", e)
            indicator = "unknown"
            description = f"Parse error: {e}"

        result = StatusResult(
            timestamp=ts,
            api_indicator=indicator,
            api_description=description,
            claude_version=version,
            response_time_ms=response_time_ms,
        )

        # Save to DB (non-fatal — statusbar updates even if DB fails)
        try:
            self._db.execute(
                "INSERT INTO api_status_log "
                "(timestamp, api_indicator, api_description, claude_version, response_time_ms) "
                "VALUES (?, ?, ?, ?, ?)",
                (result.timestamp, result.api_indicator, result.api_description,
                 result.claude_version, result.response_time_ms),
            )
            self._db.commit()

            # Prune records older than 7 days
            cutoff = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
            self._db.execute(
                "DELETE FROM api_status_log WHERE timestamp < ?", (cutoff,)
            )
            self._db.commit()
        except Exception as e:
            log.warning("Status DB write failed: %s", e)

        return result

    def get_last_status(self) -> StatusResult | None:
        """Get the most recent status from SQLite."""
        cursor = self._db.execute(
            "SELECT timestamp, api_indicator, api_description, claude_version, response_time_ms "
            "FROM api_status_log ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            return None
        return StatusResult(
            timestamp=row[0],
            api_indicator=row[1],
            api_description=row[2],
            claude_version=row[3],
            response_time_ms=row[4],
        )

    def get_status_history(self, hours: int = 24) -> list[StatusResult]:
        """Return only state TRANSITIONS within the given time window."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
        cursor = self._db.execute(
            "SELECT timestamp, api_indicator, api_description, claude_version, response_time_ms "
            "FROM api_status_log WHERE timestamp >= ? ORDER BY id ASC",
            (cutoff,),
        )
        rows = cursor.fetchall()

        transitions: list[StatusResult] = []
        prev_indicator: str | None = None

        for row in rows:
            indicator = row[1]
            if indicator != prev_indicator:
                transitions.append(StatusResult(
                    timestamp=row[0],
                    api_indicator=indicator,
                    api_description=row[2],
                    claude_version=row[3],
                    response_time_ms=row[4],
                ))
                prev_indicator = indicator

        return transitions
