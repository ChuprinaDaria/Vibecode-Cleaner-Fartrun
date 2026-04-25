"""Dead code check orchestrator — wraps Rust scan_dead_code into findings."""

from __future__ import annotations

import logging
from pathlib import Path

from core.health.models import HealthFinding, HealthReport
from core.health import tips

log = logging.getLogger(__name__)


_LANG_FOR_EXT = {
    "py": "py",
    "ts": "ts", "mts": "mts", "cts": "cts",
    "tsx": "tsx", "jsx": "jsx",
    "js": "js", "mjs": "mjs", "cjs": "cjs",
}


def parse_dead_code_files(
    health_rs,
    project_dir: str,
    rel_paths: list[str],
) -> dict[str, str]:
    """Parse a set of files via the Rust per-file API and return a
    `{rel_path: file_data_json}` mapping.

    Files that don't exist on disk, have a non-supported extension, or
    fail to read are silently skipped — callers building an incremental
    cache treat those as "drop the entry" already.
    """
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
            payload = health_rs.parse_dead_code_file_json(rel, content, lang_str)
        except BaseException as e:
            log.warning("parse_dead_code_file_json failed for %s: %s", rel, e)
            continue
        out[rel] = payload
    return out


def incremental_dead_code_scan(
    health_rs,
    project_dir: str,
    prior_state: dict[str, str],
    changed_paths: set[str],
    deleted_paths: set[str] | None = None,
):
    """Run the incremental dead-code scan.

    Parameters
    ----------
    prior_state:
        `{rel_path: file_data_json}` from the previous scan's persisted
        intermediate state.
    changed_paths:
        Files added or modified since the previous scan; their JSON in
        `prior_state` (if any) is discarded and replaced by a fresh parse.
    deleted_paths:
        Files removed since the previous scan; their JSON is discarded
        and not re-parsed.

    Returns
    -------
    (DeadCodeResult, new_state) where `new_state` is the updated
    `{rel_path: file_data_json}` mapping that callers should persist for
    the next incremental run.
    """
    deleted = deleted_paths or set()
    new_state: dict[str, str] = {
        rel: payload
        for rel, payload in prior_state.items()
        if rel not in changed_paths and rel not in deleted
    }
    fresh = parse_dead_code_files(health_rs, project_dir, sorted(changed_paths))
    new_state.update(fresh)

    payloads = list(new_state.values())
    result = health_rs.assemble_dead_code_from_json(payloads)
    return result, new_state


def run_dead_code_checks(
    report: HealthReport,
    health_rs,
    project_dir: str,
    entry_point_paths: list[str],
    *,
    scan_ctx=None,
) -> None:
    """Run dead code checks and append findings to report.

    When `scan_ctx` is provided, the cached file contents and parsed trees
    are reused — typically populated by an earlier `scan_module_map_with_context`
    call in the same run.
    """
    try:
        if scan_ctx is not None:
            result = health_rs.scan_dead_code_with_context(
                scan_ctx, project_dir, entry_point_paths,
            )
        else:
            result = health_rs.scan_dead_code(project_dir, entry_point_paths)
    except BaseException as e:
        log.error("dead_code scan error: %s", e)
        return

    # Unused imports
    report.unused_imports = [
        {"path": ui.path, "line": ui.line, "name": ui.name, "statement": ui.import_statement}
        for ui in result.unused_imports
    ]
    for ui in result.unused_imports[:20]:
        report.findings.append(HealthFinding(
            check_id="dead.unused_imports",
            title=f"Unused: {ui.name}",
            severity="medium",
            message=tips.tip_unused_import(ui.name, ui.path, ui.line),
        ))

    # Unused definitions
    report.unused_definitions = [
        {"path": ud.path, "line": ud.line, "name": ud.name, "kind": ud.kind}
        for ud in result.unused_definitions
    ]
    for ud in result.unused_definitions[:20]:
        tip_fn = tips.tip_unused_class if ud.kind == "class" else tips.tip_unused_function
        report.findings.append(HealthFinding(
            check_id="dead.unused_definitions",
            title=f"Unused {ud.kind}: {ud.name}",
            severity="medium",
            message=tip_fn(ud.name, ud.path),
        ))

    # Orphan files
    for orphan in result.orphan_files[:10]:
        report.findings.append(HealthFinding(
            check_id="dead.orphan_files",
            title=f"Orphan: {orphan}",
            severity="low",
            message=tips.tip_orphan(orphan),
        ))

    # Commented-out code
    report.commented_blocks = [
        {
            "path": cb.path,
            "start_line": cb.start_line,
            "end_line": cb.end_line,
            "line_count": cb.line_count,
            "preview": cb.preview,
        }
        for cb in result.commented_blocks
    ]
    for cb in result.commented_blocks[:10]:
        report.findings.append(HealthFinding(
            check_id="dead.commented_code",
            title=f"Commented code: {cb.path}:{cb.start_line}",
            severity="low",
            message=tips.tip_commented_code(cb.path, cb.start_line, cb.line_count),
        ))
