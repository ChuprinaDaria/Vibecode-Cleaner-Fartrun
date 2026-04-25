"""Tech debt check orchestrator — wraps Rust scan_tech_debt + git blame enrichment."""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime, timedelta

from core.health.models import HealthFinding, HealthReport

log = logging.getLogger(__name__)


def _git_blame_date(project_dir: str, path: str, line: int) -> str | None:
    """Get commit date for a specific line via git blame. Returns ISO date or None."""
    git = shutil.which("git")
    if not git:
        return None
    try:
        result = subprocess.run(
            [git, "blame", "-L", f"{line},{line}", "--porcelain", path],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if result.returncode != 0:
            return None
        for bl in result.stdout.splitlines():
            if bl.startswith("committer-time "):
                ts = int(bl.split(" ")[1])
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        return None
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _days_ago(date_str: str) -> int:
    """How many days ago was this date."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.now() - dt).days
    except ValueError:
        return 0


CHECK_IDS: tuple[str, ...] = (
    "debt.no_types",
    "debt.error_handling",
    "debt.hardcoded",
    "debt.todos",
)


def make_no_types_finding(mt) -> HealthFinding:
    parts = []
    if mt.param_count > 0:
        parts.append(f"{mt.param_count} params without types")
    if mt.missing_return:
        parts.append("no return type")
    detail = ", ".join(parts)
    return HealthFinding(
        check_id="debt.no_types",
        title=f"{mt.function_name}() — {detail}",
        severity="medium",
        message=(
            f"{mt.function_name}() in {mt.path}:{mt.line} — {detail}. "
            f"Type hints help you AND AI understand the code."
        ),
        details={"path": mt.path, "line": mt.line},
    )


def make_error_gap_finding(eg) -> HealthFinding:
    return HealthFinding(
        check_id="debt.error_handling",
        title=f"{eg.kind}: {eg.path}:{eg.line}",
        severity="medium" if eg.kind == "bare_except" else "low",
        message=f"{eg.path}:{eg.line} — {eg.description}",
        details={"path": eg.path, "line": eg.line},
    )


def make_hardcoded_finding(hc) -> HealthFinding:
    return HealthFinding(
        check_id="debt.hardcoded",
        title=f"Hardcoded {hc.kind}: {hc.path}:{hc.line}",
        severity="low",
        message=(
            f"{hc.path}:{hc.line} — {hc.value[:60]}. "
            f"Move to config or constants."
        ),
        details={"path": hc.path, "line": hc.line},
    )


def make_todo_finding(todo, project_dir: str) -> HealthFinding:
    """TODO finding with git-blame age enrichment.

    Blame call is intentionally per-finding because rate of TODOs is small
    and each one wants its own author/timestamp. On a delta scan we don't
    re-call this for unchanged files — we just carry the cached finding
    over, which preserves the original blame date string.
    """
    blame_date = _git_blame_date(project_dir, todo.path, todo.line)
    age_str = ""
    severity = "low"
    if blame_date:
        days = _days_ago(blame_date)
        if days > 30:
            severity = "medium"
            age_str = f" (from {blame_date}, {days} days ago)"
        else:
            age_str = f" (from {blame_date})"

    text_preview = todo.text[:60] if todo.text else "(no description)"
    return HealthFinding(
        check_id="debt.todos",
        title=f"{todo.kind}: {todo.path}:{todo.line}",
        severity=severity,
        message=(
            f"{todo.kind} in {todo.path}:{todo.line} — {text_preview}{age_str}"
        ),
        details={"path": todo.path, "line": todo.line},
    )


def append_findings_from_result(report: HealthReport, result, project_dir: str) -> None:
    """Append findings from a TechDebtResult (full or per-file) to report.

    The per-check caps are NOT applied here — caps are a presentation
    concern and live in the full-scan entry point (`run_tech_debt_checks`).
    Delta path appends filtered-and-rescanned findings without re-capping
    so we never silently lose findings the user already saw.
    """
    for mt in result.missing_types:
        report.findings.append(make_no_types_finding(mt))
    for eg in result.error_gaps:
        report.findings.append(make_error_gap_finding(eg))
    for hc in result.hardcoded:
        report.findings.append(make_hardcoded_finding(hc))
    for todo in result.todos:
        report.findings.append(make_todo_finding(todo, project_dir))


def run_tech_debt_checks(
    report: HealthReport,
    health_rs,
    project_dir: str,
) -> None:
    """Run the full tech-debt scan and append capped findings to report."""
    try:
        result = health_rs.scan_tech_debt(project_dir)
    except BaseException as e:
        log.error("tech_debt scan error: %s", e)
        return

    for mt in result.missing_types[:30]:
        report.findings.append(make_no_types_finding(mt))
    for eg in result.error_gaps[:20]:
        report.findings.append(make_error_gap_finding(eg))
    for hc in result.hardcoded[:20]:
        report.findings.append(make_hardcoded_finding(hc))
    for todo in result.todos[:30]:
        report.findings.append(make_todo_finding(todo, project_dir))
