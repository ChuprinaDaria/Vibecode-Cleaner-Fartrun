"""SafetyNet — composed from per-feature mixins.

Per-feature methods live in ``_save.py`` / ``_rollback.py`` /
``_pick.py`` / ``_setup.py``. This file holds the shared state and
git/SQLite helpers that the mixins call into.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from core.history import HistoryDB
from core.safety_net._pick import PickOpsMixin
from core.safety_net._rollback import RollbackOpsMixin
from core.safety_net._save import SaveOpsMixin
from core.safety_net._setup import SetupOpsMixin

log = logging.getLogger(__name__)


class _SafetyNetBase:
    """State + low-level git wrappers shared by every feature mixin."""

    def __init__(self, project_dir: str, db: HistoryDB,
                 config: dict | None = None):
        self._dir = project_dir
        self._db = db
        self._config = config or {}
        self._sn_config = self._config.get("safety_net", {})

    # --- low-level git ---

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git"] + list(args),
                cwd=self._dir,
                capture_output=True,
                text=True,
                check=check,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            log.warning("git %s timed out after 30s", args)
            if check:
                raise
            return subprocess.CompletedProcess(
                args=["git"] + list(args),
                returncode=-1,
                stdout="",
                stderr="timeout",
            )

    def _git_ok(self, *args: str) -> str:
        """Run git command, return stdout. Empty string on failure."""
        r = self._git(*args, check=False)
        return r.stdout.strip() if r.returncode == 0 else ""

    def _has_git(self) -> bool:
        return shutil.which("git") is not None

    def _is_repo(self) -> bool:
        return (Path(self._dir) / ".git").is_dir()

    def _current_branch(self) -> str:
        return self._git_ok("rev-parse", "--abbrev-ref", "HEAD") or "main"

    def _current_commit(self) -> str:
        return self._git_ok("rev-parse", "--short", "HEAD")

    def _has_changes(self) -> bool:
        r = self._git("status", "--porcelain", check=False)
        return bool(r.stdout.strip())

    def _count_tracked_files(self) -> int:
        r = self._git("ls-files", check=False)
        if r.returncode != 0:
            return 0
        return len([l for l in r.stdout.splitlines() if l.strip()])

    def _count_lines(self) -> int:
        """Count total lines in tracked source files."""
        r = self._git("ls-files", check=False)
        if r.returncode != 0:
            return 0
        total = 0
        for rel_path in r.stdout.splitlines():
            if not rel_path.strip():
                continue
            full = Path(self._dir) / rel_path
            if not full.is_file():
                continue
            # skip binary-looking files
            try:
                with open(full, encoding="utf-8", errors="ignore") as f:
                    total += sum(1 for _ in f)
            except (OSError, UnicodeDecodeError):
                pass
        return total

    def _next_tag(self) -> str:
        """Find next available savepoint-N tag."""
        r = self._git("tag", "-l", "savepoint-*", check=False)
        existing = set()
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("savepoint-"):
                try:
                    existing.add(int(line.split("-", 1)[1]))
                except ValueError:
                    pass
        n = 1
        while n in existing:
            n += 1
        return f"savepoint-{n}"

    def _next_backup_branch(self, base: str) -> str:
        """Find available backup branch name."""
        r = self._git("branch", "--list", f"{base}*", check=False)
        if not r.stdout.strip():
            return base
        suffix = 2
        while True:
            candidate = f"{base}-{suffix}"
            if candidate not in r.stdout:
                return candidate
            suffix += 1


class SafetyNet(
    SaveOpsMixin,
    RollbackOpsMixin,
    PickOpsMixin,
    SetupOpsMixin,
    _SafetyNetBase,
):
    """Save / Rollback / Pick for vibe coders.

    Composed from feature mixins so each concern (save, rollback, pick,
    repo setup) lives in its own file. The mixins call shared helpers
    (``_git``, ``_has_git``, ``_current_commit``, etc.) provided by
    ``_SafetyNetBase``.
    """
