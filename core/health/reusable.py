"""Reusable JSX-pattern orchestrator with delta-aware persistence."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


_JSX_EXTS = {"jsx", "tsx"}


def parse_reusable_files(
    health_rs,
    project_dir: str,
    rel_paths: list[str],
) -> dict[str, str]:
    """Parse a set of files via the Rust per-file API and return
    `{rel_path: payload}` for those that produced any patterns. Skips
    files outside JSX_EXTENSIONS or without analysable JSX content."""
    out: dict[str, str] = {}
    root = Path(project_dir)
    for rel in rel_paths:
        abs_path = root / rel
        ext = abs_path.suffix.lstrip(".").lower()
        if ext not in _JSX_EXTS:
            continue
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            payload = health_rs.parse_reusable_file_json(rel, content, ext)
        except BaseException as e:
            log.warning("parse_reusable_file_json failed for %s: %s", rel, e)
            continue
        if payload:
            out[rel] = payload
    return out


def incremental_reusable_scan(
    health_rs,
    project_dir: str,
    prior_state: dict[str, str],
    changed_paths: set[str],
    deleted_paths: set[str] | None = None,
):
    """Run the incremental reusable scan.

    Returns (ReusableResult, new_state). new_state may LOSE entries that
    used to produce patterns but no longer do; persist what's returned.
    """
    deleted = deleted_paths or set()
    new_state: dict[str, str] = {
        rel: payload
        for rel, payload in prior_state.items()
        if rel not in changed_paths and rel not in deleted
    }
    fresh = parse_reusable_files(health_rs, project_dir, sorted(changed_paths))
    new_state.update(fresh)

    result = health_rs.assemble_reusable_from_json(new_state)
    return result, new_state
