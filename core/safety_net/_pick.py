"""Cherry-pick files from a rollback backup branch — feature mixin."""
from __future__ import annotations

import json
import logging

from core.file_explainer import explain_file
from core.safety_net.models import PickResult, PickableFile, _SKIP_PATTERNS

log = logging.getLogger(__name__)


class PickOpsMixin:
    """List + pick files from rollback backup branches."""

    def list_pickable_files(self, backup_id: int) -> list[PickableFile]:
        backups = self._db.get_rollback_backups(self._dir)
        backup = None
        for b in backups:
            if b["id"] == backup_id:
                backup = b
                break
        if not backup:
            return []

        sp = self._db.get_save_point(backup["save_point_id"])
        if not sp:
            return []

        # git diff between save point and backup branch
        r = self._git(
            "diff", "--numstat", f"{sp['tag_name']}..{backup['backup_branch']}",
            check=False,
        )
        if r.returncode != 0:
            return []

        files = []
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            adds_str, dels_str, path = parts[0], parts[1], parts[2]

            # Skip junk
            skip = False
            for pattern in _SKIP_PATTERNS:
                if path.startswith(pattern + "/") or path == pattern:
                    skip = True
                    break
            if skip:
                continue

            adds = int(adds_str) if adds_str != "-" else 0
            dels = int(dels_str) if dels_str != "-" else 0

            # Determine status
            r2 = self._git(
                "diff", "--name-status", f"{sp['tag_name']}..{backup['backup_branch']}",
                "--", path, check=False,
            )
            status = "modified"
            if r2.stdout.strip():
                code = r2.stdout.strip().split("\t")[0]
                if code.startswith("A"):
                    status = "added"
                elif code.startswith("D"):
                    status = "deleted"

            files.append(PickableFile(
                path=path,
                status=status,
                additions=adds,
                deletions=dels,
                explanation=explain_file(path),
            ))

        return files

    def pick_files(self, backup_id: int, paths: list[str]) -> PickResult:
        backups = self._db.get_rollback_backups(self._dir)
        backup = None
        for b in backups:
            if b["id"] == backup_id:
                backup = b
                break
        if not backup:
            raise RuntimeError("backup_not_found")

        applied = []
        for path in paths:
            r = self._git(
                "checkout", backup["backup_branch"], "--", path,
                check=False,
            )
            if r.returncode == 0:
                applied.append(path)
            else:
                log.warning("Could not pick %s: %s", path, r.stderr.strip())

        if not applied:
            raise RuntimeError("no_files_picked")

        self._git("add", *applied)
        file_list = ", ".join(applied[:5])
        if len(applied) > 5:
            file_list += f" (+{len(applied) - 5} more)"
        self._git("commit", "-m",
                  f"picked from {backup['backup_branch']}: {file_list}")

        commit_hash = self._current_commit()

        # Update DB
        picked = json.loads(backup.get("picked_files", "[]"))
        picked.extend(applied)
        self._db.update_picked_files(backup_id, json.dumps(picked))

        self._db.bump_git_education(self._dir, "picks_count")

        return PickResult(files_applied=applied, commit_hash=commit_hash)
