"""Repo bootstrap helpers — git init, .gitignore, user.name/email."""
from __future__ import annotations

from pathlib import Path


class SetupOpsMixin:
    """Lazy git-repo setup so non-git projects can opt in."""

    def ensure_git(self) -> bool:
        if not self._has_git():
            return False
        if self._is_repo():
            return True
        r = self._git("init", check=False)
        if r.returncode == 0:
            self._db.bump_git_education(self._dir, "git_initialized")
            return True
        return False

    def fix_gitignore(self, patterns: list[str]) -> None:
        gitignore = Path(self._dir) / ".gitignore"
        existing = ""
        if gitignore.exists():
            existing = gitignore.read_text(errors="ignore")

        lines = existing.splitlines()
        added = []
        for pattern in patterns:
            if pattern not in existing:
                lines.append(pattern)
                added.append(pattern)

        if added:
            gitignore.write_text("\n".join(lines) + "\n")
            self._db.bump_git_education(self._dir, "gitignore_created")

    def set_git_user(self, name: str, email: str) -> None:
        self._git("config", "user.name", name)
        self._git("config", "user.email", email)
