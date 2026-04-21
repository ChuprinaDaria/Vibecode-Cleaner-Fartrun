"""Shared git subprocess helper for health checks."""

from __future__ import annotations

import shutil
import subprocess


def run_git(project_dir: str, *args: str) -> str | None:
    """Run a git command. Returns stdout or None on error."""
    git = shutil.which("git")
    if not git:
        return None
    try:
        result = subprocess.run(
            [git, *args],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def is_git_repo(project_dir: str) -> bool:
    """Check if directory is a git repo."""
    output = run_git(project_dir, "rev-parse", "--is-inside-work-tree")
    return output is not None and output.strip() == "true"
