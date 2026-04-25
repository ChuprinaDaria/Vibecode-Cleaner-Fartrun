"""Duplicates orchestrator with delta-aware persistence.

Per-file state is the normalized line set produced by the Rust scanner;
the cross-file ngram-matching phase runs over the full set on every run
but the per-file normalization is the expensive part for large repos
(re-reading every file, stripping comments/imports, computing line
hashes), and that's what we now skip for unchanged files on warm
re-scans.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


# Same set as `crate::common::SOURCE_EXTENSIONS` filtered to files
# `normalize_line` actually has rules for. Anything else falls through to
# the JS branch in the Rust normaliser, which is also what scan_duplicates
# does today.
_SOURCE_EXTS = {
    "py",
    "js", "mjs", "cjs", "jsx",
    "ts", "tsx", "mts", "cts",
    "rs", "go", "rb", "php", "swift", "cs",
    "c", "h", "cpp", "hpp", "cc", "cxx", "hxx",
    "java", "kt", "kts",
}


def parse_duplicates_files(
    health_rs,
    project_dir: str,
    rel_paths: list[str],
) -> dict[str, str]:
    """Parse a set of files via the Rust per-file API and return
    `{rel_path: payload}` for those big enough to be analysed.

    Files below the MIN_DUPLICATE_LINES threshold come back with an
    empty-string payload — we treat that the same as 'not present' and
    skip them so the cache stays clean.
    """
    out: dict[str, str] = {}
    root = Path(project_dir)
    for rel in rel_paths:
        abs_path = root / rel
        ext = abs_path.suffix.lstrip(".").lower()
        if ext not in _SOURCE_EXTS:
            continue
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            payload = health_rs.parse_duplicates_file_json(rel, content, ext)
        except BaseException as e:
            log.warning("parse_duplicates_file_json failed for %s: %s", rel, e)
            continue
        if payload:
            out[rel] = payload
    return out


def incremental_duplicates_scan(
    health_rs,
    project_dir: str,
    prior_state: dict[str, str],
    changed_paths: set[str],
    deleted_paths: set[str] | None = None,
):
    """Run the incremental duplicates scan.

    Returns (DuplicatesResult, new_state). new_state may LOSE entries that
    the prior run had but that have since fallen below the size threshold;
    callers should persist exactly what's returned, not a union.
    """
    deleted = deleted_paths or set()
    new_state: dict[str, str] = {
        rel: payload
        for rel, payload in prior_state.items()
        if rel not in changed_paths and rel not in deleted
    }
    fresh = parse_duplicates_files(health_rs, project_dir, sorted(changed_paths))
    new_state.update(fresh)

    payloads = list(new_state.values())
    result = health_rs.assemble_duplicates_from_json(payloads)
    return result, new_state
