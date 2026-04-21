"""Phase 11 — UX Sanity: custom JSX/TSX checks for vibe-coded projects."""

from __future__ import annotations

import json
import logging

from core.health.models import HealthFinding, HealthReport

log = logging.getLogger(__name__)


def run_ux_sanity_checks(report: HealthReport, health_rs, project_dir: str) -> None:
    """Run UX sanity checks via Rust scanner and append findings to report."""
    try:
        raw = health_rs.scan_ux_sanity(project_dir)
    except BaseException as e:
        log.error("ux_sanity scan error: %s", e)
        return

    try:
        issues = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        log.error("ux_sanity JSON parse error: %s", e)
        return

    for issue in issues[:30]:
        report.findings.append(HealthFinding(
            check_id=f"ux.{issue['rule']}",
            title=f"{issue['rule']}: {issue['file']}:{issue['line']}",
            severity="medium" if issue.get("severity") == "warning" else "high",
            message=issue["message"],
            details={
                "file": issue["file"],
                "line": issue["line"],
                "column": issue["column"],
            },
        ))
