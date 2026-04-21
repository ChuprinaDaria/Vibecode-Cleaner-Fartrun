"""Dead code check orchestrator — wraps Rust scan_dead_code into findings."""

from __future__ import annotations

import logging

from core.health.models import HealthFinding, HealthReport
from core.health import tips

log = logging.getLogger(__name__)


def run_dead_code_checks(
    report: HealthReport,
    health_rs,
    project_dir: str,
    entry_point_paths: list[str],
) -> None:
    """Run dead code checks and append findings to report."""
    try:
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
