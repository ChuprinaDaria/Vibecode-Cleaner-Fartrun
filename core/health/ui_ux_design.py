"""Phase 7 — UI/UX Design Quality scanning.

Two layers:
  1. QSS scanner (built-in) — parses setStyleSheet() strings in Python/Qt
     projects, detects AI slop patterns and design quality issues.
  2. Web scanners (via npx, auto-download):
     - impeccable  → AI slop detection for web projects
     - stylelint   → CSS linting (170+ rules)
     - lighthouse  → accessibility + performance + SEO (manual)
     - pa11y       → WCAG compliance (manual)
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from core.health.models import HealthFinding, HealthReport
from core.health import tips

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_npx() -> bool:
    return shutil.which("npx") is not None


def _run_json(cmd: list[str], cwd: str, timeout: int = 120) -> dict | list | None:
    """Run a command, parse JSON stdout. Returns None on any failure."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        log.debug("ui_ux tool %s failed: %s", cmd[0], e)
    return None


def _has_web_frontend(project_dir: str) -> bool:
    """Does this project have web CSS/HTML/JSX/TSX files?"""
    root = Path(project_dir)
    for ext in ("*.css", "*.scss", "*.html", "*.jsx", "*.tsx", "*.vue", "*.svelte"):
        if any(root.rglob(ext)):
            return True
    return False


def _has_qt_styles(project_dir: str) -> bool:
    """Does this project have PyQt/PySide with setStyleSheet calls?"""
    root = Path(project_dir)
    for py_file in root.rglob("*.py"):
        if ".venv" in py_file.parts or "node_modules" in py_file.parts:
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
            if "setStyleSheet" in text or "StyleSheet" in text:
                return True
        except OSError:
            continue
    return False


def _no_node_finding(check_id: str) -> HealthFinding:
    return HealthFinding(
        check_id=check_id,
        title="Node.js not found",
        severity="low",
        message=tips.tip_install_node(),
    )


# ---------------------------------------------------------------------------
# QSS Scanner — built-in, no external tools needed
# ---------------------------------------------------------------------------

# AI slop patterns in CSS/QSS — things every LLM generates
_SLOP_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, rule_id, human description)
    (r"#[89a-f][0-9a-f]00[89a-f][89a-f]|purple|#800080|#9b59b6|#6c5ce7|#a855f7",
     "purple-gradient", "Purple/violet color — the #1 AI-generated color choice"),
    (r"font-family:.*\bInter\b", "inter-font",
     "Inter font — every LLM defaults to it"),
    (r"font-family:.*\bRoboto\b", "roboto-font",
     "Roboto font — second most common AI default"),
    (r"border-radius:\s*(16|20|24|28|32)\s*px", "huge-radius",
     "Oversized border-radius — AI loves making everything a pill"),
    (r"box-shadow:.*0\s+0\s+\d+px\s+\d+px.*rgba\(", "glow-shadow",
     "Glow/bloom shadow — dark glow effect AI adds to everything"),
    (r"backdrop-filter:\s*blur", "backdrop-blur",
     "Backdrop blur (glassmorphism) — AI's favorite 'modern' effect"),
    (r"linear-gradient.*(?:#[89a-f]|purple|violet|indigo)", "purple-gradient-bg",
     "Purple gradient background — classic AI slop"),
]

# Design quality issues
_QUALITY_PATTERNS: list[tuple[str, str, str]] = [
    (r"padding:\s*[0-3]px", "cramped-padding",
     "Padding under 4px — too cramped, looks amateur"),
    (r"font-size:\s*[0-9]px\b", "tiny-font",
     "Font under 10px — too small to read comfortably"),
    (r"font-size:\s*(8|9)px", "tiny-font-critical",
     "Font 8-9px — almost unreadable"),
    (r"color:\s*#[0-9a-f]{3,6}.*background:\s*#[0-9a-f]{3,6}|"
     r"background:\s*#[0-9a-f]{3,6}.*color:\s*#[0-9a-f]{3,6}",
     "contrast-check", "Check text/background contrast ratio"),
    (r"!important", "important-abuse",
     "!important in styles — sign of specificity war or lazy override"),
    (r"margin:\s*-\d+px", "negative-margin",
     "Negative margin — fragile layout hack, breaks on resize"),
]

# Compiled for performance
_SLOP_RE = [(re.compile(p, re.IGNORECASE), rid, desc) for p, rid, desc in _SLOP_PATTERNS]
_QUALITY_RE = [(re.compile(p, re.IGNORECASE), rid, desc) for p, rid, desc in _QUALITY_PATTERNS]

# Extract strings from setStyleSheet(...) calls — handles f-strings, concatenation
_STYLESHEET_RE = re.compile(
    r'setStyleSheet\s*\(\s*'
    r'(?:'
    r'f?"([^"]*)"'    # double-quoted
    r"|f?'([^']*)'"   # single-quoted
    r')',
    re.DOTALL,
)

# Also catch module-level style constants (X_STYLE = "...")
_STYLE_CONST_RE = re.compile(
    r'^[A-Z_]+STYLE[A-Z_]*\s*=\s*\(\s*$',
    re.MULTILINE,
)


def _extract_qss_blocks(file_path: Path) -> list[tuple[int, str]]:
    """Extract (line_number, css_text) from setStyleSheet calls and STYLE constants."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    blocks: list[tuple[int, str]] = []

    # setStyleSheet("...") inline calls
    for m in _STYLESHEET_RE.finditer(text):
        css = m.group(1) or m.group(2) or ""
        if css.strip():
            line_no = text[:m.start()].count("\n") + 1
            blocks.append((line_no, css))

    # Module-level style strings — scan all string literals in lines with CSS properties
    for i, line in enumerate(text.splitlines(), 1):
        if any(kw in line for kw in ("background:", "color:", "border:", "font-",
                                      "padding:", "margin:", "border-radius:")):
            # Extract the string content
            for m in re.finditer(r'[f]?"([^"]{10,})"', line):
                css = m.group(1)
                if any(p in css for p in ("background", "color", "border", "font", "padding")):
                    blocks.append((i, css))

    return blocks


def _scan_qss(project_dir: str) -> list[HealthFinding]:
    """Scan Python/Qt files for AI slop and design quality issues in QSS."""
    root = Path(project_dir)
    findings: list[HealthFinding] = []
    slop_count = 0
    quality_count = 0
    seen: set[tuple[str, str]] = set()  # (file:line, rule_id) dedup

    skip_dirs = {".venv", "venv", "node_modules", "__pycache__", ".git", ".tox"}

    for py_file in root.rglob("*.py"):
        if any(part in skip_dirs for part in py_file.parts):
            continue

        blocks = _extract_qss_blocks(py_file)
        if not blocks:
            continue

        try:
            rel = str(py_file.relative_to(root))
        except ValueError:
            rel = str(py_file)

        for line_no, css_text in blocks:
            # Check AI slop patterns
            for pattern, rule_id, description in _SLOP_RE:
                if pattern.search(css_text):
                    key = (f"{rel}:{line_no}", rule_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    slop_count += 1
                    findings.append(HealthFinding(
                        check_id="uiux.qss_slop",
                        title=f"AI Slop: {rule_id} ({rel}:{line_no})",
                        severity="medium",
                        message=tips.tip_qss_slop(rule_id, description, rel, line_no),
                        details={"file": rel, "line": line_no, "rule": rule_id,
                                 "css": css_text[:200]},
                    ))

            # Check design quality patterns
            for pattern, rule_id, description in _QUALITY_RE:
                if pattern.search(css_text):
                    key = (f"{rel}:{line_no}", rule_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    quality_count += 1
                    findings.append(HealthFinding(
                        check_id="uiux.qss_quality",
                        title=f"Design: {rule_id} ({rel}:{line_no})",
                        severity="low",
                        message=tips.tip_qss_quality(rule_id, description, rel, line_no),
                        details={"file": rel, "line": line_no, "rule": rule_id,
                                 "css": css_text[:200]},
                    ))

    # Summary finding
    if slop_count == 0 and quality_count == 0 and findings == []:
        findings.append(HealthFinding(
            check_id="uiux.qss_slop",
            title="QSS Style Check",
            severity="info",
            message="No AI slop or design issues in your Qt styles. Clean.",
        ))
    elif slop_count > 0 or quality_count > 0:
        findings.insert(0, HealthFinding(
            check_id="uiux.qss_slop",
            title=f"Style Scan: {slop_count} AI slop, {quality_count} quality issues",
            severity="medium" if slop_count > 0 else "low",
            message=tips.tip_qss_summary(slop_count, quality_count),
        ))

    return findings


# ---------------------------------------------------------------------------
# Web scanners (npx-based, for web projects only)
# ---------------------------------------------------------------------------

def _scan_impeccable(project_dir: str) -> list[HealthFinding]:
    """Run npx impeccable detect — auto-downloads on first run."""
    if not _has_npx():
        return [_no_node_finding("uiux.impeccable")]

    data = _run_json(
        ["npx", "--yes", "impeccable", "detect", "--fast", "--json", "."],
        cwd=project_dir, timeout=120,
    )
    if not data:
        return []

    findings: list[HealthFinding] = []
    issues = data if isinstance(data, list) else data.get("issues", data.get("results", []))

    for issue in issues:
        if isinstance(issue, dict):
            category = issue.get("category", "design")
            rule = issue.get("rule", issue.get("id", "unknown"))
            message = issue.get("message", issue.get("description", str(issue)))
            file_path = issue.get("file", issue.get("path", ""))
            line = issue.get("line", "")

            is_slop = "slop" in category.lower() or "slop" in rule.lower()
            severity = "medium" if is_slop else "low"

            title_prefix = "AI Slop" if is_slop else "Design Quality"
            location = f"{file_path}:{line}" if file_path and line else file_path

            findings.append(HealthFinding(
                check_id="uiux.impeccable",
                title=f"{title_prefix}: {rule}" + (f" ({location})" if location else ""),
                severity=severity,
                message=tips.tip_impeccable(rule, message, is_slop),
                details=issue,
            ))

    if not issues and data:
        findings.append(HealthFinding(
            check_id="uiux.impeccable",
            title="AI Slop Check",
            severity="info",
            message="No AI slop patterns detected. Your design doesn't look like every other AI-generated site.",
        ))

    return findings


def _scan_stylelint(project_dir: str) -> list[HealthFinding]:
    """Run npx stylelint — auto-downloads on first run."""
    if not _has_npx():
        return [_no_node_finding("uiux.stylelint")]

    root = Path(project_dir)
    css_files = list(root.rglob("*.css")) + list(root.rglob("*.scss"))
    if not css_files:
        return []

    data = _run_json(
        ["npx", "--yes", "stylelint", "**/*.css", "**/*.scss",
         "--formatter", "json", "--allow-empty-input"],
        cwd=project_dir, timeout=60,
    )
    if not data:
        return []

    findings: list[HealthFinding] = []
    results = data if isinstance(data, list) else []

    error_count = 0
    warning_count = 0
    sample_issues: list[dict] = []

    for file_result in results:
        if not isinstance(file_result, dict):
            continue
        file_path = file_result.get("source", "")
        for warning in file_result.get("warnings", []):
            sev = warning.get("severity", "warning")
            if sev == "error":
                error_count += 1
            else:
                warning_count += 1
            if len(sample_issues) < 5:
                sample_issues.append({
                    "file": file_path,
                    "line": warning.get("line", ""),
                    "rule": warning.get("rule", ""),
                    "text": warning.get("text", ""),
                })

    if error_count + warning_count == 0:
        findings.append(HealthFinding(
            check_id="uiux.stylelint",
            title="CSS Quality",
            severity="info",
            message="CSS is clean — no stylelint issues found.",
        ))
        return findings

    severity = "medium" if error_count > 0 else "low"
    findings.append(HealthFinding(
        check_id="uiux.stylelint",
        title=f"CSS Quality: {error_count} errors, {warning_count} warnings",
        severity=severity,
        message=tips.tip_stylelint(error_count, warning_count),
        details={"errors": error_count, "warnings": warning_count},
    ))

    for issue in sample_issues:
        try:
            rel = str(Path(issue["file"]).relative_to(root))
        except ValueError:
            rel = issue["file"]
        findings.append(HealthFinding(
            check_id="uiux.stylelint",
            title=f"CSS: {issue['rule']} ({rel}:{issue['line']})",
            severity="low",
            message=issue["text"],
            details=issue,
        ))

    return findings


def _scan_lighthouse(project_dir: str) -> list[HealthFinding]:
    """Lighthouse needs a running dev server — hint to run manually."""
    if not _has_npx():
        return [_no_node_finding("uiux.lighthouse")]

    pkg_json = Path(project_dir) / "package.json"
    if not pkg_json.exists():
        return []

    return [HealthFinding(
        check_id="uiux.lighthouse",
        title="Lighthouse — run manually",
        severity="info",
        message=tips.tip_lighthouse_available(),
        details={"hint": "npx lighthouse http://localhost:3000 --output=json"},
    )]


def _scan_pa11y(project_dir: str) -> list[HealthFinding]:
    """pa11y needs a running dev server — hint to run manually."""
    if not _has_npx():
        return [_no_node_finding("uiux.pa11y")]

    pkg_json = Path(project_dir) / "package.json"
    if not pkg_json.exists():
        return []

    return [HealthFinding(
        check_id="uiux.pa11y",
        title="pa11y — run manually",
        severity="info",
        message=tips.tip_pa11y_available(),
        details={"hint": "npx pa11y http://localhost:3000 --reporter json"},
    )]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_ui_ux_checks(report: HealthReport, project_dir: str) -> None:
    """Phase 7 — UI/UX Design Quality checks."""
    has_web = _has_web_frontend(project_dir)
    has_qt = _has_qt_styles(project_dir)

    if not has_web and not has_qt:
        log.debug("No frontend/UI files found, skipping UI/UX checks")
        return

    # QSS scanner — always runs for Qt projects (built-in, no deps)
    if has_qt:
        try:
            report.findings.extend(_scan_qss(project_dir))
        except Exception as e:
            log.error("qss scan error: %s", e)

    # Web scanners — only for web projects
    if has_web:
        for scanner in (_scan_impeccable, _scan_stylelint, _scan_lighthouse, _scan_pa11y):
            try:
                report.findings.extend(scanner(project_dir))
            except Exception as e:
                log.error("%s scan error: %s", scanner.__name__, e)
