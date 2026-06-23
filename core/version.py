"""Fartrun version — single source of truth.

Import this everywhere instead of hardcoding version strings::

    from core.version import __version__
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path


def _read_version() -> str:
    """Resolve the version with three-tier fallback."""
    # Tier 1: installed package metadata (pip install / editable install)
    try:
        return importlib.metadata.version("claude-monitor")  # matches pyproject.toml [project].name
    except importlib.metadata.PackageNotFoundError:
        pass

    # Tier 2: pyproject.toml in the repo root (running from source)
    try:
        import tomllib
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with open(pyproject, "rb") as f:
            return tomllib.load(f).get("project", {}).get("version", "0.0.0")
    except Exception:
        pass

    # Tier 3: PyInstaller bundle or anything else
    return "0.0.0"


__version__: str = _read_version()
