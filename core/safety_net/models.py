"""Shared data classes + constants for the Safety Net feature."""
from __future__ import annotations

from dataclasses import dataclass, field

# Files / dirs to skip when listing pickable files.
_SKIP_PATTERNS = {
    "node_modules", "__pycache__", ".git", ".env", ".venv",
    "venv", "env", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".next", ".nuxt",
}


@dataclass
class SavePointResult:
    id: int
    commit_hash: str
    tag_name: str
    file_count: int
    lines_total: int
    warnings_fixed: list[str] = field(default_factory=list)


@dataclass
class RollbackPreview:
    files_affected: int
    current_branch: str
    target_commit: str
    target_label: str


@dataclass
class RollbackResult:
    backup_branch: str
    backup_commit: str
    files_restored: int


@dataclass
class PickableFile:
    path: str
    status: str          # "added", "modified", "deleted"
    additions: int
    deletions: int
    explanation: str


@dataclass
class PickResult:
    files_applied: list[str]
    commit_hash: str
