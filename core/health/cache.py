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
import re
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from core.health.git_utils import is_git_repo, run_git
from core.health.models import HealthFinding, HealthReport

# Two-char status code (X = staging, Y = worktree) followed by a space,
# followed by the path. Robust to run_git's .strip() that eats the leading
# space of unstaged-only entries (` M path` → `M path`).
_PORCELAIN_LINE = re.compile(r"^[ ?ACDMRTU!]{1,2}\s+(.*)$")

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
    would make a cached scan misleading).

    Modifications under `.fartrun/` are ignored — that directory is where
    the tool itself writes its output (HEALTH-REPORT-*.md, etc.), so its
    contents are downstream of the scan, not user code that would change
    the result.
    """
    if not is_git_repo(project_dir):
        return None
    head = run_git(project_dir, "rev-parse", "HEAD")
    if not head:
        return None
    status = run_git(project_dir, "status", "--porcelain")
    if status:
        # Filter out fartrun's own output. We can't rely on column slicing
        # because `run_git` already strips leading whitespace, so the
        # ` M path` form arrives as `M path`. Regex extracts the path
        # robustly across status formats.
        for line in status.splitlines():
            m = _PORCELAIN_LINE.match(line)
            if not m:
                # Unparseable line — be conservative and treat as dirty.
                return None
            path = m.group(1).strip().strip('"')
            if " -> " in path:
                # Rename: `old -> new`. The new path is what's on disk.
                path = path.split(" -> ", 1)[1].strip().strip('"')
            if path != ".fartrun" and not path.startswith(".fartrun/"):
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
    # Per-file intermediate state for incremental scans. Each row is one
    # source file's serialized parser output, keyed by which scanner
    # produced it (e.g. 'dead_code') so different scanners can persist
    # independently without colliding.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS file_data_cache (
            project_key TEXT NOT NULL,
            head_hash TEXT NOT NULL,
            scanner TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            rel_path TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (project_key, head_hash, scanner, schema_version, rel_path)
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
    without, every entry. Returns the count of scan_cache rows removed
    (file_data_cache is wiped too but not counted, since it's an
    implementation detail of incremental scans)."""
    try:
        conn = _connect()
        try:
            if project_dir is not None:
                key = _project_key(project_dir)
                cur = conn.execute(
                    "DELETE FROM scan_cache WHERE project_key=?",
                    (key,),
                )
                conn.execute(
                    "DELETE FROM file_data_cache WHERE project_key=?",
                    (key,),
                )
            else:
                cur = conn.execute("DELETE FROM scan_cache")
                conn.execute("DELETE FROM file_data_cache")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.clear: sqlite error: %s", e)
        return 0


def list_cached_hashes(project_dir: str) -> set[str]:
    """Return every git HEAD hash that currently has a cached scan for this
    project under the active schema version. Used by git_delta to find the
    most recent ancestor commit that we can incrementally update from."""
    key = _project_key(project_dir)
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT head_hash FROM scan_cache "
                "WHERE project_key=? AND schema_version=?",
                (key, CACHE_SCHEMA_VERSION),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.list_cached_hashes: sqlite error: %s", e)
        return set()
    return {row[0] for row in rows}


def get_file_data(
    project_dir: str,
    head_hash_value: str,
    scanner: str,
) -> dict[str, str]:
    """Load a `{rel_path: payload}` mapping for a given scanner at a
    specific commit hash. Returns an empty dict on miss or sqlite error
    so callers can drop into a clean full scan without special-casing."""
    key = _project_key(project_dir)
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT rel_path, payload FROM file_data_cache "
                "WHERE project_key=? AND head_hash=? AND scanner=? "
                "AND schema_version=?",
                (key, head_hash_value, scanner, CACHE_SCHEMA_VERSION),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.get_file_data: sqlite error: %s", e)
        return {}
    return {rel: payload for rel, payload in rows}


def put_file_data(
    project_dir: str,
    head_hash_value: str,
    scanner: str,
    state: dict[str, str],
) -> bool:
    """Replace the persisted `{rel_path: payload}` set for `(head_hash,
    scanner)`. Existing rows for the same key are deleted first so the
    cache stays in sync with what the orchestrator just produced."""
    key = _project_key(project_dir)
    try:
        conn = _connect()
        try:
            conn.execute(
                "DELETE FROM file_data_cache "
                "WHERE project_key=? AND head_hash=? AND scanner=? "
                "AND schema_version=?",
                (key, head_hash_value, scanner, CACHE_SCHEMA_VERSION),
            )
            if state:
                conn.executemany(
                    "INSERT INTO file_data_cache "
                    "(project_key, head_hash, scanner, schema_version, "
                    " rel_path, payload) VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (key, head_hash_value, scanner, CACHE_SCHEMA_VERSION,
                         rel, payload)
                        for rel, payload in state.items()
                    ],
                )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.put_file_data: sqlite error: %s", e)
        return False
    return True


def get_at(project_dir: str, head_hash_value: str) -> HealthReport | None:
    """Look up a cached report for a *specific* commit hash, regardless of
    whether the working tree currently sits at that hash. This is what
    git_delta uses to retrieve the report from an ancestor commit so it can
    patch it with diff-derived findings."""
    key = _project_key(project_dir)
    try:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT payload FROM scan_cache "
                "WHERE project_key=? AND head_hash=? AND schema_version=?",
                (key, head_hash_value, CACHE_SCHEMA_VERSION),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("scan_cache.get_at: sqlite error: %s", e)
        return None
    if not row:
        return None
    try:
        return _deserialize(row[0])
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        log.warning("scan_cache.get_at: deserialize failed: %s", e)
        return None
