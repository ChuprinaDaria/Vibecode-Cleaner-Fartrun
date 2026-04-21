"""Brake System checks — unfinished work, test health, scope creep, overengineering."""

from __future__ import annotations

import logging
from pathlib import Path

from core.health.models import HealthFinding, HealthReport
from core.health.git_utils import run_git as _run_git

log = logging.getLogger(__name__)


def check_unfinished_work(report: HealthReport, project_dir: str) -> None:
    """Check 4.1 — uncommitted files, stashes, dirty state."""
    dirty_output = _run_git(project_dir, "status", "--porcelain")
    dirty_files = []
    if dirty_output:
        dirty_files = [l[3:].strip() for l in dirty_output.splitlines() if l.strip()]

    stash_output = _run_git(project_dir, "stash", "list")
    stash_count = len(stash_output.splitlines()) if stash_output else 0

    if not dirty_files and stash_count == 0:
        return

    parts = []
    if dirty_files:
        parts.append(f"{len(dirty_files)} uncommitted files")
    if stash_count:
        parts.append(f"{stash_count} stashed changes")

    severity = "medium" if len(dirty_files) > 5 else "low"

    report.findings.append(HealthFinding(
        check_id="brake.unfinished",
        title=f"Unfinished work: {', '.join(parts)}",
        severity=severity,
        message=(
            f"You have {', '.join(parts)}. "
            f"Maybe finish this before starting something new?"
        ),
    ))


def check_test_health(report: HealthReport, project_dir: str) -> None:
    """Check 4.2 — find test files, detect framework, count."""
    root = Path(project_dir)

    test_patterns = [
        "test_*.py", "*_test.py",
        "*.test.js", "*.spec.js",
        "*.test.ts", "*.spec.ts",
        "*.test.jsx", "*.spec.jsx",
        "*.test.tsx", "*.spec.tsx",
        # Go stdlib testing convention
        "*_test.go",
        # Rust (tests/ dir handled below)
        # Ruby RSpec / minitest
        "*_spec.rb", "*_test.rb",
        # Java / Kotlin — JUnit / Kotest
        "*Test.java", "*Tests.java",
        "*Test.kt", "*Tests.kt",
        # PHP — PHPUnit
        "*Test.php",
        # Elixir — ExUnit
        "*_test.exs",
        # C# / .NET
        "*Tests.cs", "*Test.cs",
    ]

    test_files: list[str] = []
    for pattern in test_patterns:
        for match_path in root.rglob(pattern):
            rel = str(match_path.relative_to(root))
            # Skip node_modules, venv, etc
            if any(skip in rel for skip in [
                "node_modules", ".venv", "venv", "__pycache__", "fixtures",
            ]):
                continue
            test_files.append(rel)

    # Rust tests/ dir under Cargo project (integration tests)
    if (root / "Cargo.toml").exists():
        tests_dir = root / "tests"
        if tests_dir.is_dir():
            for rs in tests_dir.rglob("*.rs"):
                rel = str(rs.relative_to(root))
                if "target" not in rel:
                    test_files.append(rel)

    # Detect framework
    framework = "unknown"
    has_conftest = (root / "conftest.py").exists() or any(
        (root / d / "conftest.py").exists() for d in ["tests", "test"]
    )
    has_pytest_ini = (root / "pytest.ini").exists() or (root / "pyproject.toml").exists()
    has_jest = (root / "jest.config.js").exists() or (root / "jest.config.ts").exists()
    has_go_mod = (root / "go.mod").exists()
    has_cargo = (root / "Cargo.toml").exists()

    if has_conftest or has_pytest_ini:
        framework = "pytest"
    elif has_jest:
        framework = "jest"
    elif has_go_mod and any(f.endswith("_test.go") for f in test_files):
        framework = "go test"
    elif has_cargo:
        framework = "cargo test"

    if not test_files:
        report.findings.append(HealthFinding(
            check_id="brake.tests",
            title="No tests found",
            severity="high",
            message=(
                "Zero test files in this project. "
                "No tests = no safety net. One broken change and you won't know until production."
            ),
        ))
    else:
        py_tests = [f for f in test_files if f.endswith(".py")]
        js_tests = [f for f in test_files if not f.endswith(".py")]
        parts = []
        if py_tests:
            parts.append(f"{len(py_tests)} Python")
        if js_tests:
            parts.append(f"{len(js_tests)} JS/TS")

        report.findings.append(HealthFinding(
            check_id="brake.tests",
            title=f"Tests: {len(test_files)} files ({framework})",
            severity="info",
            message=f"{len(test_files)} test files found ({', '.join(parts)}). Framework: {framework}.",
        ))


def check_scope_creep(report: HealthReport, project_dir: str) -> None:
    """Check 4.4 — analyze recent git activity for scope creep."""
    log_output = _run_git(
        project_dir, "log", "--since=8 hours ago", "--stat", "--oneline"
    )
    if not log_output:
        return

    commits = 0
    files_created = 0
    files_deleted = 0
    files_modified = 0

    for line in log_output.splitlines():
        line = line.strip()
        if not line:
            continue

        # Commit line: hash message
        if not line.startswith(" ") and "|" not in line and "=>" not in line:
            if "file" not in line and "insertion" not in line and "deletion" not in line:
                commits += 1
                continue

        # Stat line: " file | N ++" or summary line
        if "file" in line and ("changed" in line or "insertion" in line or "deletion" in line):
            continue  # summary line

        if "|" in line:
            files_modified += 1
        elif "(new)" in line.lower() or "create" in line.lower():
            files_created += 1
        elif "(gone)" in line.lower() or "delete" in line.lower():
            files_deleted += 1

    if commits == 0:
        return

    # Detect scope creep: lots of new files, nothing deleted or fixed
    if files_created > 5 and files_deleted == 0:
        report.findings.append(HealthFinding(
            check_id="brake.scope_creep",
            title=f"Scope creep: +{files_created} files, -0 deleted",
            severity="medium",
            message=(
                f"Last 8 hours: {commits} commits, {files_created} new files, "
                f"0 deleted. You're adding but not cleaning up."
            ),
        ))
    elif commits > 0:
        report.findings.append(HealthFinding(
            check_id="brake.scope_creep",
            title=f"Session: {commits} commits, ~{files_modified} files touched",
            severity="info",
            message=(
                f"Last 8 hours: {commits} commits, "
                f"~{files_modified} files modified."
            ),
        ))


def check_overengineering(report: HealthReport, health_rs, project_dir: str) -> None:
    """Check 4.5 — overengineering via Rust scanner."""
    try:
        result = health_rs.scan_overengineering(project_dir)
    except Exception as e:
        log.error("overengineering scan error: %s", e)
        return

    for issue in result.issues[:15]:
        report.findings.append(HealthFinding(
            check_id="brake.overengineering",
            title=f"{issue.kind}: {issue.path}",
            severity="low",
            message=issue.description,
        ))


def check_opensource_first(report: HealthReport, project_dir: str) -> None:
    """Check 4.3 — reminder to search for existing solutions before building.

    Simply shows a reminder on every scan. The point is not detection —
    it's a habit nudge: before you build something, check if it exists.
    """
    report.findings.append(HealthFinding(
        check_id="brake.opensource_check",
        title="Before building — search first",
        severity="info",
        message=(
            "Before writing a new feature: google it. Check GitHub repos, PyPI, npm. "
            "Someone probably already built what you need. "
            "Don't reinvent the wheel — steal the wheel."
        ),
    ))


def run_brake_checks(
    report: HealthReport,
    health_rs,
    project_dir: str,
) -> None:
    """Run all brake system checks."""
    check_unfinished_work(report, project_dir)
    check_test_health(report, project_dir)
    check_scope_creep(report, project_dir)
    check_opensource_first(report, project_dir)
    if health_rs is not None:
        check_overengineering(report, health_rs, project_dir)
