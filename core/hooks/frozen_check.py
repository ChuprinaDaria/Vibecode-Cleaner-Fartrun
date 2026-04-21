"""PreToolUse hook — block Edit/Write on frozen files.

Claude Code invokes this script before executing Edit/Write/MultiEdit tools.
Protocol: JSON on stdin, exit code decides — 0 allow, 2 block (stderr shown
to the user).

We read the current working directory from the payload (``cwd``), open the
project's fartrun DB, and check if the target path is in ``frozen_files``.
If yes we block with a human-readable message.

Failures are non-blocking: if anything goes wrong we exit 0 so we never
brick the user's workflow just because fartrun itself is broken.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _project_paths(cwd: str, target_rel: str) -> list[str]:
    """Return candidate paths to check against the frozen list.

    The DB stores paths as given by the GUI — usually relative to project
    root. We check both the raw value and its project-relative form.
    """
    candidates = {target_rel}
    try:
        target_abs = Path(target_rel)
        if not target_abs.is_absolute():
            target_abs = Path(cwd) / target_rel
        target_abs = target_abs.resolve()
        cwd_path = Path(cwd).resolve()
        if cwd_path in target_abs.parents or cwd_path == target_abs:
            candidates.add(str(target_abs.relative_to(cwd_path)))
        candidates.add(str(target_abs))
    except (OSError, ValueError):
        pass
    return [c for c in candidates if c]


def _extract_paths(tool_name: str, tool_input: dict) -> list[str]:
    """Pull the file_path(s) out of the tool input."""
    if tool_name in ("Edit", "Write"):
        fp = tool_input.get("file_path")
        return [fp] if isinstance(fp, str) else []
    if tool_name == "MultiEdit":
        fp = tool_input.get("file_path")
        return [fp] if isinstance(fp, str) else []
    return []


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Can't parse → don't block

    tool_name = payload.get("tool_name") or payload.get("tool") or ""
    tool_input = payload.get("tool_input") or payload.get("input") or {}
    cwd = payload.get("cwd") or os.getcwd()

    targets = _extract_paths(tool_name, tool_input)
    if not targets:
        return 0

    try:
        # Lazy imports — hook must start fast
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from core.history import HistoryDB
    except Exception:
        return 0

    db_path = os.environ.get("FARTRUN_DB_PATH")
    try:
        db = HistoryDB(db_path) if db_path else HistoryDB()
        db.init()
        frozen = {f["path"] for f in db.get_frozen_files(cwd)}
    except Exception:
        return 0

    if not frozen:
        return 0

    for target in targets:
        for candidate in _project_paths(cwd, target):
            if candidate in frozen:
                sys.stderr.write(
                    f"fartrun: '{candidate}' is in your Don't Touch list. "
                    f"If you really want to edit it, unlock it first in "
                    f"fartrun → Save Points.\n"
                )
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
