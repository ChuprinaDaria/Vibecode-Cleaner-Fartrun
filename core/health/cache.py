"""On-disk cache for health scan reports.

Reports are keyed by (project_dir, git HEAD hash, schema version). When the
working tree has uncommitted changes, or the project is not a git repo, the
cache is transparently bypassed so callers always observe the actual disk
state.

The schema version exists so that bumping it invalidates every old entry
without manual cleanup — bump it whenever HealthReport's serialization
shape changes or scanner internals diverge meaningfully from prior runs.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from core.health.git_utils import is_git_repo, run_git
from core.health.models import HealthFinding, HealthReport

log = logging.getLogger(__name__)

# Bump when serialization shape or scanner output changes.
CACHE_SCHEMA_VERSION = 1


def cache_dir() -> Path:
    """XDG-compliant cache dir: $XDG_CACHE_HOME/fartrun or ~/.cache/fartrun."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    p = Path(base) / "fartrun"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_db_path() -> Path:
    return cache_dir() / "scan_cache.db"


def _project_key(project_dir: str) -> str:
    """Normalized project identity. Resolves symlinks so two different paths
    pointing at the same directory share a single cache entry."""
    return str(Path(project_dir).resolve())


def head_hash(project_dir: str) -> str | None:
    """Return the git HEAD commit hash, or None when we should bypass cache:
    not a git repo, no HEAD yet, or working tree is dirty (uncommitted changes
    would make a cached scan misleading)."""
    if not is_git_repo(project_dir):
        return None
    head = run_git(project_dir, "rev-parse", "HEAD")
    if not head:
        return None
    status = run_git(project_dir, "status", "--porcelain")
    if status:
        # Any modification, addition, deletion or untracked file. Bypass
        # cache so the scan reflects current disk state.
        return None
    return head.strip()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(cache_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_cache (
            project_key TEXT NOT NULL,
            head_hash TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            created_at REAL NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (project_key, head_hash, schema_version)
        )
        """
    )
    return conn


def _serialize(report: HealthReport) -> str:
    return json.dumps(
        {
            "project_dir": report.project_dir,
            "findings": [asdict(f) for f in report.findings],
            "file_tree": report.file_tree,
            "entry_points": report.entry_points,
            "module_map": report.module_map,
            "monsters": report.monsters,
            "configs": report.configs,
            "unused_imports": report.unused_imports,
            "unused_definitions": report.unused_definitions,
            "commented_blocks": report.commented_blocks,
        }
    )


def _deserialize(payload: str) -> HealthReport:
    data = json.loads(payload)
    report = HealthReport(project_dir=data["project_dir"])
    report.findings = [HealthFinding(**f) for f in data["findings"]]
    report.file_tree = data["file_tree"]
    report.entry_points = data["entry_points"]
    report.module_map = data["module_map"]
    report.monsters = data["monsters"]
    report.configs = data["configs"]
    report.unused_imports = data["unused_imports"]
    report.unused_definitions = data["unused_definitions"]
    report.commented_blocks = data["commented_blocks"]
    return report


def get(project_dir: str) -> HealthReport | None:
    """Look up a cached report. Returns None on miss, or when caching is
    bypassed (no git, dirty tree, sqlite error, or schema mismatch)."""
    h = head_hash(project_dir)
    if not h:
        return None
    key = _project_key(project_dir)
    try:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT payload FROM scan_cache "
                "WHERE project_key=? AND head_hash=? AND schema_version=?",
                (key, h, CACHE_SCHEMA_VERSION),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.get: sqlite error: %s", e)
        return None
    if not row:
        return None
    try:
        return _deserialize(row[0])
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        log.warning("scan_cache.get: deserialize failed (%s) — treating as miss", e)
        return None


def put(project_dir: str, report: HealthReport) -> bool:
    """Store report keyed by current HEAD. Returns False when caching is
    bypassed (no git, dirty tree) or the write failed."""
    h = head_hash(project_dir)
    if not h:
        return False
    key = _project_key(project_dir)
    try:
        payload = _serialize(report)
    except (TypeError, ValueError) as e:
        log.warning("scan_cache.put: report not JSON-serializable: %s", e)
        return False
    try:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO scan_cache "
                "(project_key, head_hash, schema_version, created_at, payload) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, h, CACHE_SCHEMA_VERSION, time.time(), payload),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.put: sqlite error: %s", e)
        return False
    return True


def clear(project_dir: str | None = None) -> int:
    """Remove cached entries. With project_dir, only entries for that project;
    without, every entry. Returns rows removed (0 on error)."""
    try:
        conn = _connect()
        try:
            if project_dir is not None:
                cur = conn.execute(
                    "DELETE FROM scan_cache WHERE project_key=?",
                    (_project_key(project_dir),),
                )
            else:
                cur = conn.execute("DELETE FROM scan_cache")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.clear: sqlite error: %s", e)
        return 0
