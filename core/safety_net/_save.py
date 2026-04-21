"""Save-point creation, validation, and listing — feature mixin.

Mixed into ``SafetyNet`` via ``manager.py``. Methods rely on the
shared helpers (``self._git``, ``self._has_git``, etc.) provided by
``_SafetyNetBase``.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.safety_net.models import SavePointResult


class SaveOpsMixin:
    """Save Point creation + listing."""

    def can_save(self) -> tuple[bool, str]:
        if not self._has_git():
            return False, "git_not_installed"
        if not self._is_repo():
            return False, "no_git_repo"
        if not self._has_changes():
            return False, "no_changes"
        return True, ""

    def pre_save_warnings(self) -> list[dict]:
        warnings = []
        gitignore = Path(self._dir) / ".gitignore"

        # .env tracked by git?
        env_file = Path(self._dir) / ".env"
        if env_file.exists():
            r = self._git("ls-files", ".env", check=False)
            if r.stdout.strip():
                warnings.append({
                    "type": "env_tracked",
                    "message": "safety_warn_env",
                    "fix": "add_gitignore",
                    "pattern": ".env",
                })

        # node_modules without .gitignore?
        nm = Path(self._dir) / "node_modules"
        if nm.is_dir():
            has_ignore = False
            if gitignore.exists():
                content = gitignore.read_text(errors="ignore")
                has_ignore = "node_modules" in content
            if not has_ignore:
                warnings.append({
                    "type": "node_modules",
                    "message": "safety_warn_node_modules",
                    "fix": "add_gitignore",
                    "pattern": "node_modules/",
                })

        return warnings

    def create_save_point(self, label: str) -> SavePointResult:
        if not self._is_repo():
            raise RuntimeError("Not a git repository")

        # git add + commit
        self._git("add", ".")
        tag_name = self._next_tag()
        commit_msg = f"Save Point: {label}"

        r = self._git("commit", "-m", commit_msg, check=False)
        if r.returncode != 0:
            if "please tell me who you are" in r.stderr.lower() or \
               "author identity unknown" in r.stderr.lower():
                raise RuntimeError("git_config_missing")
            if "nothing to commit" in r.stdout.lower() or "nothing to commit" in r.stderr.lower():
                raise RuntimeError("no_changes")
            raise RuntimeError(f"git commit failed: {r.stderr}")

        commit_hash = self._current_commit()
        self._git("tag", tag_name)

        file_count = self._count_tracked_files()
        lines_total = self._count_lines()

        # Save to DB
        sp_id = self._db.add_save_point(
            timestamp=datetime.now().isoformat(),
            label=label,
            project_dir=self._dir,
            branch=self._current_branch(),
            commit_hash=commit_hash,
            tag_name=tag_name,
            file_count=file_count,
            lines_total=lines_total,
        )

        # Enforce max save points
        max_sp = self._sn_config.get("max_save_points", 20)
        self._cleanup_old_save_points(max_sp)

        self._db.bump_git_education(self._dir, "saves_count")

        return SavePointResult(
            id=sp_id,
            commit_hash=commit_hash,
            tag_name=tag_name,
            file_count=file_count,
            lines_total=lines_total,
        )

    def _cleanup_old_save_points(self, max_count: int) -> None:
        points = self._db.get_save_points(self._dir, limit=max_count + 50)
        if len(points) <= max_count:
            return
        to_remove = points[max_count:]
        for sp in to_remove:
            # Remove git tag
            self._git("tag", "-d", sp["tag_name"], check=False)
            self._db.delete_save_point(sp["id"])

    def get_save_points(self, limit: int = 20) -> list[dict]:
        return self._db.get_save_points(self._dir, limit)
