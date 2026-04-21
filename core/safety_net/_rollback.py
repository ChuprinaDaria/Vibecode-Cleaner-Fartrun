"""Rollback (incl. selective rollback) — feature mixin."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.safety_net.models import (
    RollbackPreview, RollbackResult, _SKIP_PATTERNS,
)


class RollbackOpsMixin:
    """Rollback to save points, with optional file-level pickback."""

    def can_rollback(self, save_point_id: int) -> tuple[bool, str]:
        sp = self._db.get_save_point(save_point_id)
        if not sp:
            return False, "save_point_not_found"

        # Check if merge in progress
        merge_head = Path(self._dir) / ".git" / "MERGE_HEAD"
        if merge_head.exists():
            return False, "merge_in_progress"

        # Check if we're already at this commit
        current = self._current_commit()
        if current == sp["commit_hash"]:
            if not self._has_changes():
                return False, "already_at_save_point"

        return True, ""

    def rollback_preview(self, save_point_id: int) -> RollbackPreview | None:
        sp = self._db.get_save_point(save_point_id)
        if not sp:
            return None

        # Count files that differ
        r = self._git("diff", "--name-only", sp["commit_hash"], check=False)
        files_in_diff = len([l for l in r.stdout.splitlines() if l.strip()])

        # Also count uncommitted changes
        r2 = self._git("status", "--porcelain", check=False)
        uncommitted = len([l for l in r2.stdout.splitlines() if l.strip()])

        return RollbackPreview(
            files_affected=max(files_in_diff, uncommitted),
            current_branch=self._current_branch(),
            target_commit=sp["commit_hash"],
            target_label=sp["label"],
        )

    def rollback(self, save_point_id: int) -> RollbackResult:
        sp = self._db.get_save_point(save_point_id)
        if not sp:
            raise RuntimeError("save_point_not_found")

        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H-%M")
        backup_base = f"backup/{timestamp}"
        backup_branch = self._next_backup_branch(backup_base)

        # Commit current changes if any
        if self._has_changes():
            self._git("add", ".")
            self._git("commit", "-m",
                      f"backup before rollback to {sp['tag_name']}",
                      check=False)

        backup_commit = self._current_commit()

        # Count changed files for metadata
        r = self._git("diff", "--name-only", sp["commit_hash"], check=False)
        files_changed = len([l for l in r.stdout.splitlines() if l.strip()])

        # Create backup branch at current position
        self._git("branch", backup_branch)

        # Reset to save point
        self._git("reset", "--hard", sp["tag_name"])

        files_restored = self._count_tracked_files()

        # Save to DB
        self._db.add_rollback_backup(
            timestamp=now.isoformat(),
            project_dir=self._dir,
            save_point_id=save_point_id,
            backup_branch=backup_branch,
            backup_commit=backup_commit,
            files_changed=files_changed,
        )

        self._db.bump_git_education(self._dir, "rollbacks_count")

        return RollbackResult(
            backup_branch=backup_branch,
            backup_commit=backup_commit,
            files_restored=files_restored,
        )

    def get_changes_since(self, save_point_id: int) -> list:
        """Files changed since a save point (including untracked).

        Returns list of FileChange (path/additions/deletions/status) for
        the Smart Rollback dialog to feed to feature_grouper.
        """
        from core.feature_grouper import FileChange

        sp = self._db.get_save_point(save_point_id)
        if not sp:
            return []

        def _is_junk(path: str) -> bool:
            return any(path.startswith(p + "/") or path == p
                       for p in _SKIP_PATTERNS)

        changes: dict[str, FileChange] = {}

        # Tracked changes: diff working tree against save-point commit
        r = self._git("diff", "--numstat", sp["commit_hash"], check=False)
        r_status = self._git("diff", "--name-status", sp["commit_hash"],
                             check=False)
        status_map: dict[str, str] = {}
        for line in r_status.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                code, path = parts
                status_map[path] = {"A": "added", "D": "deleted"}.get(
                    code.strip()[:1], "modified"
                )

        if r.returncode == 0:
            for line in r.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                adds_str, dels_str, path = parts[0], parts[1], parts[2]
                if _is_junk(path):
                    continue
                adds = int(adds_str) if adds_str.isdigit() else 0
                dels = int(dels_str) if dels_str.isdigit() else 0
                changes[path] = FileChange(
                    path=path, additions=adds, deletions=dels,
                    status=status_map.get(path, "modified"),
                )

        # Untracked files — count their line count as "additions"
        r_untracked = self._git("ls-files", "--others", "--exclude-standard",
                                check=False)
        if r_untracked.returncode == 0:
            for path in r_untracked.stdout.splitlines():
                path = path.strip()
                if not path or _is_junk(path) or path in changes:
                    continue
                try:
                    lines = (Path(self._dir) / path).read_text(
                        errors="ignore"
                    ).count("\n") + 1
                except Exception:
                    lines = 0
                changes[path] = FileChange(
                    path=path, additions=lines, deletions=0, status="added",
                )

        return list(changes.values())

    def rollback_with_picks(self, save_point_id: int,
                            keep_paths: list[str]) -> RollbackResult:
        """Rollback to save point BUT re-apply selected paths from the backup.

        Flow:
        1. Normal rollback() — commits current work, branches as backup,
           hard-resets to save point.
        2. For each keep_path, checkout that file from the backup commit
           back into the working tree.
        3. Commit the kept files as a single "selective rollback" commit
           so the history is clean and you can Pick more later if needed.
        """
        result = self.rollback(save_point_id)
        if not keep_paths:
            return result

        applied: list[str] = []
        for path in keep_paths:
            r = self._git("checkout", result.backup_commit, "--", path,
                          check=False)
            if r.returncode == 0:
                applied.append(path)

        if applied:
            self._git("add", *applied, check=False)
            commit_msg = (
                f"selective rollback: keep {len(applied)} file(s) "
                f"from save_point_{save_point_id}"
            )
            self._git("commit", "-m", commit_msg, check=False)

        return result
