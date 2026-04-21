"""Auto-detect projects from ~/.claude/projects/ directory."""
from __future__ import annotations
import logging
from pathlib import Path
from core.history import HistoryDB

log = logging.getLogger(__name__)
_LAST_PROJECT_KEY = "last_project_dir"


def _decode_claude_path(encoded: str) -> str:
    """Decode Claude Code project dir name back to real filesystem path.

    Claude encodes paths like: -home-dchuprina-claude-monitor
    But dashes also appear in real dir names (claude-monitor, N-bohatska).
    Strategy: split by '-', try progressively joining segments with '-'
    and check which paths actually exist on disk.
    """
    if not encoded.startswith("-"):
        return encoded

    # Remove leading dash, split into segments
    segments = encoded[1:].split("-")
    if not segments:
        return "/" + encoded[1:]

    # Greedy approach: build path left-to-right, at each step check if
    # joining next segment with '/' (deeper dir) or '-' (same dir) is valid.
    # Prefer '/' when both exist (deeper path is more specific).
    path = "/" + segments[0]
    for seg in segments[1:]:
        candidate_slash = path + "/" + seg
        candidate_dash = path + "-" + seg
        # Check which parent paths exist to make the right choice
        slash_parent_exists = Path(candidate_slash).parent.is_dir()
        if slash_parent_exists and Path(candidate_slash).exists():
            path = candidate_slash
        elif Path(candidate_dash).exists():
            path = candidate_dash
        elif slash_parent_exists:
            # Parent exists but this segment doesn't yet — could be deeper
            # But check if dash variant's parent exists and dash is valid dir
            path = candidate_slash
        else:
            # Parent for '/' doesn't exist — must be dash (part of dir name)
            path = candidate_dash

    return path


def detect_projects(claude_dir: str) -> list[dict]:
    """Scan claude_dir/projects/ for project directories.
    Returns list of {path, mtime, name} sorted by most recent first.
    Claude stores projects as encoded paths: -home-user-project
    """
    projects_dir = Path(claude_dir) / "projects"
    if not projects_dir.is_dir():
        return []
    results = []
    for entry in projects_dir.iterdir():
        if not entry.is_dir():
            continue
        decoded = _decode_claude_path(entry.name)
        try:
            mtime = max(
                (f.stat().st_mtime for f in entry.rglob("*") if f.is_file()),
                default=entry.stat().st_mtime,
            )
        except OSError:
            mtime = 0
        real_path = Path(decoded)
        if real_path.is_dir():
            results.append({"path": decoded, "mtime": mtime, "name": real_path.name})
        else:
            results.append({"path": decoded, "mtime": mtime, "name": entry.name})
    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results


def get_last_project(db: HistoryDB) -> str | None:
    return db.get_state(_LAST_PROJECT_KEY)


def save_last_project(db: HistoryDB, path: str) -> None:
    db.set_state(_LAST_PROJECT_KEY, path)
