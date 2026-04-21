"""Health check utilities."""

from __future__ import annotations

from pathlib import Path

_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".tox",
              "dist", "build", ".next", ".nuxt", "target", ".mypy_cache", "env"}


def has_files_with_ext(root: Path, ext: str, max_depth: int = 3) -> bool:
    """Check if directory contains files with given extension, with depth limit."""
    return _walk_limited(root, ext, max_depth, find_one=True) > 0


def _walk_limited(root: Path, ext: str, max_depth: int, find_one: bool = False, _depth: int = 0) -> int:
    """Walk directory with depth limit and skip list. Returns count."""
    if _depth > max_depth:
        return 0
    count = 0
    try:
        for item in root.iterdir():
            if item.is_dir():
                if item.name in _SKIP_DIRS:
                    continue
                count += _walk_limited(item, ext, max_depth, find_one, _depth + 1)
                if find_one and count > 0:
                    return count
            elif item.suffix == f".{ext}":
                count += 1
                if find_one:
                    return count
    except (PermissionError, OSError):
        pass
    return count
