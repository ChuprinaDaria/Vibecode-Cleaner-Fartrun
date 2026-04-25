"""Module-map orchestrator with delta-aware persistence.

Wraps the Rust scanner so warm re-scans skip the per-file import
extraction phase: prior raw imports for unchanged files are replayed
from `file_data_cache`, only changed files are re-parsed, and the
cross-file resolve + graph + circular + orphan analysis runs against
the merged set.

Falls back to a full scan + state collection when no usable cache
exists, so the very first run on a project still populates the cache
without paying the parse cost twice.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


_LANG_FOR_EXT = {
    "py": "py",
    "ts": "ts", "mts": "mts", "cts": "cts",
    "tsx": "tsx", "jsx": "jsx",
    "js": "js", "mjs": "mjs", "cjs": "cjs",
}


def parse_module_map_files(
    health_rs,
    project_dir: str,
    rel_paths: list[str],
) -> dict[str, str]:
    """Parse a set of files via the Rust per-file API and return a
    `{rel_path: imports_json}` mapping. Skips paths that are missing,
    unreadable, or in a language module_map doesn't analyse."""
    out: dict[str, str] = {}
    root = Path(project_dir)
    for rel in rel_paths:
        abs_path = root / rel
        ext = abs_path.suffix.lstrip(".").lower()
        lang_str = _LANG_FOR_EXT.get(ext)
        if lang_str is None:
            continue
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            payload = health_rs.parse_module_map_file_json(rel, content, lang_str)
        except BaseException as e:
            log.warning("parse_module_map_file_json failed for %s: %s", rel, e)
            continue
        out[rel] = payload
    return out


def incremental_module_map_scan(
    health_rs,
    project_dir: str,
    entry_point_paths: list[str],
    prior_state: dict[str, str],
    changed_paths: set[str],
    deleted_paths: set[str] | None = None,
    all_files: list[str] | None = None,
):
    """Run the incremental module_map scan.

    `all_files` is the full set of files in the project (including ones
    in non-supported languages); this matters for orphan detection and
    package-root inference. The orchestrator captures it from the file
    walk it does anyway.

    Returns (ModuleMapResult, new_state) — `new_state` is the
    `{rel_path: imports_json}` mapping the caller should persist for
    the next incremental run.
    """
    deleted = deleted_paths or set()
    new_state: dict[str, str] = {
        rel: payload
        for rel, payload in prior_state.items()
        if rel not in changed_paths and rel not in deleted
    }
    fresh = parse_module_map_files(health_rs, project_dir, sorted(changed_paths))
    new_state.update(fresh)

    result = health_rs.assemble_module_map_from_json(
        project_dir,
        entry_point_paths,
        new_state,
        all_files,
    )
    return result, new_state
