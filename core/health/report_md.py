"""Generate Markdown health report for Claude / AI agent consumption.

Produces a checklist-style .md file with:
- Recommended action order (plan for Claude)
- Actionable fixes grouped by priority with "why it matters"
- Grouped TODOs and duplicates (less tokens, same info)
- Specific file:line references
- Context7 documentation snippets where available
- Known scanner limitations (possible false positives)
- Instructions for AI usage
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from core.health.models import HealthFinding, HealthReport


def _get_git_remote_url(project_dir: str) -> str | None:
    """Get HTTPS URL of origin remote for the scanned project."""
    try:
        result = subprocess.run(
            ["git", "-C", project_dir, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        url = result.stdout.strip()
        if not url:
            return None
        # Convert git@github.com:user/repo.git → https://github.com/user/repo
        if url.startswith("git@"):
            url = url.replace(":", "/").replace("git@", "https://")
        if url.endswith(".git"):
            url = url[:-4]
        return url
    except Exception:
        return None


# Known false positive patterns — warn the user
_FP_WARNINGS: dict[str, str] = {
    "dead.unused_imports": (
        "Scanner may flag imports used only as type annotations in complex "
        "generics, or side-effect imports (e.g. model registration). "
        "Verify before deleting — check if the import is used in type hints, "
        "decorators, or has side effects on import."
    ),
    "dead.unused_definitions": (
        "Functions/methods called dynamically (getattr, signals, event handlers) "
        "or exposed as public API may be flagged. Also: celery tasks discovered "
        "by name, pytest fixtures in conftest.py, and Django/DRF auto-discovered "
        "methods. Verify the function isn't called via string name or framework magic."
    ),
    "map.modules": (
        "Orphan detection doesn't track dynamic imports (importlib, __import__), "
        "lazy imports inside functions, or framework auto-discovery (Django admin "
        "autodiscover, pytest conftest). Files like `main.jsx`, `index.js`, "
        "`mongo-init.js` are often entry points loaded by bundlers or Docker — "
        "not real orphans."
    ),
    "debt.no_types": (
        "FastAPI/Flask endpoints with @router decorators get return types from "
        "the decorator (response_model=). Scanner skips these, but custom "
        "decorators may still trigger false alerts."
    ),
    "debt.no_reuse": (
        "Reusable pattern detection skips HTML/RN primitives, but custom design "
        "system components with className may be intentionally repeated "
        "(e.g. consistent spacing divs). Use judgment."
    ),
    "framework.django_secret_key": (
        "If SECRET_KEY is loaded via env (config(), env(), os.environ) with an "
        "insecure default — scanner flags as medium, not critical. The real fix "
        "is removing the default entirely so the app crashes without the env var."
    ),
}

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "warning": "🟡",
    "info": "ℹ️",
}

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "warning", "info"]

# "Why it matters" context per check category — helps Claude prioritize
_CATEGORY_CONTEXT: dict[str, str] = {
    "map.monsters": (
        "Monster files are hard for AI to work with — context window limits mean "
        "Claude can't see the whole file at once. Split to improve AI-assisted development."
    ),
    "dead.unused_imports": (
        "Unused imports add noise, slow down IDE indexing, and can mask real "
        "dependencies. Safe to remove after verifying they're not side-effect imports."
    ),
    "dead.unused_definitions": (
        "Dead code confuses AI assistants and developers. If a function isn't called, "
        "it's either forgotten or accessed via framework magic — verify before deleting."
    ),
    "dead.duplicates": (
        "Duplicated code means fixing a bug in one place leaves the same bug alive "
        "in the copy. Extract shared logic into a common module."
    ),
    "debt.todos": (
        "Old TODOs are broken promises. If they've been there for weeks, either "
        "implement them or delete them — stale TODOs train you to ignore all TODOs."
    ),
    "debt.no_types": (
        "Missing type hints make AI code generation less accurate — Claude guesses "
        "parameter types instead of knowing them. Add types to improve AI output."
    ),
    "debt.no_reuse": (
        "Repeated UI patterns should be extracted into shared components. "
        "Less code to maintain, consistent look, easier for AI to modify."
    ),
    "debt.error_handling": (
        "Bare except/empty catch blocks silently swallow errors. When something "
        "breaks, you won't know what or where. Log or handle specifically."
    ),
    "debt.hardcoded": (
        "Hardcoded values (URLs, ports, keys) break when environments change. "
        "Extract to config/env vars."
    ),
    "debt.outdated_deps": (
        "Outdated dependencies may have known vulnerabilities. Major version gaps "
        "also make future upgrades harder — incremental updates are cheaper."
    ),
    "brake.overengineering": (
        "Single-method classes and deep nesting add complexity without value. "
        "Simplify to plain functions where possible."
    ),
    "brake.tests": (
        "No tests means every change is a gamble. Start with smoke tests for "
        "critical paths — even one test is infinitely better than zero."
    ),
    "git.status": (
        "Uncommitted changes can be lost. Commit early, commit often."
    ),
    "git.commits": (
        "Giant commits are hard to review, hard to revert, and hard for AI to understand. "
        "Keep commits focused on one change."
    ),
    "framework.django_secret_key": (
        "Insecure SECRET_KEY means anyone can forge sessions, CSRF tokens, and "
        "signed cookies. This is a security vulnerability, not a style issue."
    ),
    "framework.django_debug": (
        "DEBUG=True in production exposes stack traces, SQL queries, and settings "
        "to anyone who triggers an error. Never deploy with DEBUG on."
    ),
    "framework.docker_latest_tag": (
        "`:latest` tags are mutable — your build can break tomorrow because a base "
        "image changed. Pin versions for reproducible builds."
    ),
    "framework.heavy_dir_in_git": (
        "Large directories (venv/, node_modules/) tracked in git bloat the repo "
        "permanently. Add to .gitignore and remove from tracking."
    ),
}


def _group_findings(findings: list[HealthFinding]) -> dict[str, list[HealthFinding]]:
    """Group findings by severity, ordered by priority."""
    groups: dict[str, list[HealthFinding]] = {}
    for sev in _SEVERITY_ORDER:
        matched = [f for f in findings if f.severity == sev]
        if matched:
            groups[sev] = matched
    return groups


def _finding_to_checklist_item(f: HealthFinding) -> str:
    """Convert a finding to a markdown checklist item with fix info."""
    lines = [f"- [ ] **{f.title}**"]

    if f.message:
        desc = f.message.split(". ")[0] + "."
        lines.append(f"  - {desc}")

    # Context7 fix recommendation
    rec = f.details.get("fix_recommendation")
    if rec:
        source = f.details.get("context7_source", "docs")
        lines.append(f"  - **Fix ({source} docs):**")
        rec_lines = [rl for rl in rec.split("\n") if rl.strip()][:12]
        for rl in rec_lines:
            lines.append(f"    {rl}")

    return "\n".join(lines)


def _group_todos(findings: list[HealthFinding]) -> list[str]:
    """Group TODO findings by file instead of listing each separately."""
    by_file: dict[str, list[HealthFinding]] = defaultdict(list)
    for f in findings:
        # Extract file path from title like "TODO: internal/station/manager.go:212"
        parts = f.title.split(": ", 1)
        if len(parts) == 2:
            filepath = parts[1].rsplit(":", 1)[0]
            by_file[filepath].append(f)
        else:
            by_file["other"].append(f)

    lines = []
    for filepath, todos in by_file.items():
        if len(todos) == 1:
            lines.append(_finding_to_checklist_item(todos[0]))
            lines.append("")
            continue

        # Extract age from first todo message
        age = ""
        msg = todos[0].message
        if "days ago" in msg:
            age_start = msg.rfind("(from ")
            if age_start != -1:
                age = " " + msg[age_start:]

        lines.append(f"- [ ] **{len(todos)} TODOs in {filepath}**{age}")
        for t in todos:
            line_part = t.title.split(":")[-1] if ":" in t.title else "?"
            # Extract TODO text from message
            todo_text = ""
            if " — " in t.message:
                todo_text = t.message.split(" — ", 1)[1].split(" (from")[0]
            lines.append(f"  - :{line_part} — {todo_text}")
        lines.append("")
    return lines


def _group_duplicates(findings: list[HealthFinding]) -> list[str]:
    """Group duplicate findings by file pair."""
    by_pair: dict[str, list[HealthFinding]] = defaultdict(list)
    for f in findings:
        # Title: "Duplicate: fileA ↔ fileB (N lines)"
        title = f.title
        if "↔" in title:
            pair_part = title.split(": ", 1)[1].rsplit(" (", 1)[0]
            by_pair[pair_part].append(f)
        else:
            by_pair[title].append(f)

    lines = []
    for pair, dupes in by_pair.items():
        if len(dupes) == 1:
            lines.append(_finding_to_checklist_item(dupes[0]))
            lines.append("")
            continue

        total_lines = 0
        detail_parts = []
        for d in dupes:
            # Extract line count from title "(N lines)"
            if "(" in d.title and "lines)" in d.title:
                n = d.title.rsplit("(", 1)[1].split(" ")[0]
                try:
                    total_lines += int(n)
                except ValueError:
                    pass
            # Extract line refs from message
            msg = d.message
            if ":" in msg and " and " in msg:
                left = msg.split(":")[1].split(" ")[0] if ":" in msg else "?"
                right = msg.rsplit(":", 1)[1].split(".")[0] if ":" in msg else "?"
                n_str = d.title.rsplit("(", 1)[1].split(" ")[0] if "(" in d.title else "?"
                detail_parts.append(f"{left}↔{right} ({n_str}L)")

        lines.append(
            f"- [ ] **{len(dupes)} duplicate blocks: {pair}**"
        )
        lines.append(
            f"  - Total: ~{total_lines} duplicated lines. "
            f"Extract shared logic into a common module."
        )
        if detail_parts:
            lines.append(f"  - Lines: {', '.join(detail_parts)}")
        lines.append("")
    return lines


def _group_reusable(findings: list[HealthFinding]) -> list[str]:
    """Format reusable pattern findings with actionable component names."""
    lines = []
    for f in findings:
        # Extract element name from title like "<div class='loading'> in 4 files (4x)"
        title = f.title
        element = title.split(">")[0] + ">" if ">" in title else title

        # Suggest component name based on class
        component_name = None
        if "class='" in element:
            class_val = element.split("class='")[1].split("'")[0]
            # Convert class to PascalCase component name
            parts = class_val.replace("-", " ").replace("_", " ").split()
            component_name = "".join(p.capitalize() for p in parts)

        if component_name:
            lines.append(f"- [ ] **Extract reusable component: <{component_name} />**")
        else:
            lines.append(f"- [ ] **Extract reusable pattern: {element}**")

        if f.message:
            desc = f.message.split(". ")[0] + "."
            lines.append(f"  - {desc}")
        lines.append("")
    return lines


def _build_action_plan(grouped: dict[str, list[HealthFinding]]) -> list[str]:
    """Build recommended action order from grouped findings."""
    lines = ["## Recommended action order", ""]
    step = 1

    for sev in ["critical", "high"]:
        if sev not in grouped:
            continue
        items = grouped[sev]
        # Summarize what types of findings
        categories = defaultdict(int)
        for f in items:
            if "Monster" in f.title:
                categories["split monster files"] += 1
            elif "Duplicate" in f.title:
                categories["extract duplicates"] += 1
            elif f.check_id.startswith("framework."):
                categories["fix framework issues"] += 1
            elif f.check_id.startswith("debt.outdated"):
                categories["update dependencies"] += 1
            else:
                categories["fix " + f.check_id.split(".")[-1]] += 1

        for cat, count in categories.items():
            lines.append(f"{step}. **{sev.upper()}:** {cat} ({count} items)")
            step += 1

    if "medium" in grouped:
        medium = grouped["medium"]
        categories = defaultdict(int)
        for f in medium:
            if "Monster" in f.title:
                categories["split large files"] += 1
            elif "Duplicate" in f.title:
                categories["extract duplicates"] += 1
            elif "TODO" in f.title:
                categories["resolve old TODOs"] += 1
            elif f.check_id == "debt.no_reuse":
                categories["extract reusable components"] += 1
            elif f.check_id == "dead.unused_imports":
                categories["remove unused imports"] += 1
            elif f.check_id == "dead.unused_definitions":
                categories["remove dead code"] += 1
            elif f.check_id.startswith("ux."):
                categories["fix UI/UX issues"] += 1
            elif f.check_id.startswith("debt."):
                categories["reduce tech debt"] += 1
            elif f.check_id.startswith("framework."):
                categories["fix framework config"] += 1
            else:
                categories[f.check_id.split(".")[-1]] += 1

        # Sort by count descending, show top items
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            lines.append(f"{step}. {cat} ({count} items)")
            step += 1

    lines.append("")
    return lines


def _get_category_context(check_id: str) -> str | None:
    """Get 'why it matters' context for a check category."""
    if check_id in _CATEGORY_CONTEXT:
        return _CATEGORY_CONTEXT[check_id]
    # Try prefix match
    for prefix, ctx in _CATEGORY_CONTEXT.items():
        if check_id.startswith(prefix):
            return ctx
    return None


def _collect_fp_warnings(findings: list[HealthFinding]) -> list[str]:
    """Collect relevant FP warnings based on which check_ids appear."""
    seen_prefixes: set[str] = set()
    warnings = []
    for f in findings:
        for prefix, warning in _FP_WARNINGS.items():
            if f.check_id.startswith(prefix) or prefix in f.check_id:
                if prefix not in seen_prefixes:
                    seen_prefixes.add(prefix)
                    warnings.append(f"- **{prefix}**: {warning}")
    return warnings


def generate_report_md(report: HealthReport) -> str:
    """Generate a full Markdown health report."""
    project_name = Path(report.project_dir).name
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    actionable = [f for f in report.findings if f.severity != "info"]
    grouped = _group_findings(actionable)

    counts: dict[str, int] = {}
    for f in report.findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    lines: list[str] = []

    # ── Header ──
    lines.append(f"# Health Report: {project_name}")
    lines.append("")
    lines.append(f"Scanned: {now}")
    lines.append(f"Total findings: {len(report.findings)} "
                 f"(actionable: {len(actionable)})")
    lines.append("")

    # Summary bar
    summary_parts = []
    for sev in _SEVERITY_ORDER:
        if sev in counts:
            emoji = _SEVERITY_EMOJI.get(sev, "")
            summary_parts.append(f"{emoji} {sev}: {counts[sev]}")
    lines.append(" | ".join(summary_parts))
    lines.append("")

    # Project context
    if report.file_tree:
        total = report.file_tree.get("total_files", "?")
        lines.append(f"**Files:** {total}")
    if report.entry_points:
        ep_names = [ep.get("path", "?") for ep in report.entry_points[:3]]
        lines.append(f"**Entry points:** {', '.join(ep_names)}")
    lines.append("")

    # ── 1. Action plan ──
    lines.extend(_build_action_plan(grouped))
    lines.append("---")
    lines.append("")

    # ── 2. Findings by severity with category context ──
    for sev, findings in grouped.items():
        emoji = _SEVERITY_EMOJI.get(sev, "")
        lines.append(f"## {emoji} {sev.upper()} ({len(findings)})")
        lines.append("")

        # Group findings by check_id for context headers
        by_category: dict[str, list[HealthFinding]] = defaultdict(list)
        for f in findings:
            by_category[f.check_id].append(f)

        for check_id, cat_findings in by_category.items():
            # Add "why it matters" context once per category
            ctx = _get_category_context(check_id)
            if ctx:
                lines.append(f"> {ctx}")
                lines.append("")

            # Special grouping for TODOs
            if check_id == "debt.todos":
                lines.extend(_group_todos(cat_findings))
                continue

            # Special grouping for duplicates
            if check_id == "dead.duplicates":
                lines.extend(_group_duplicates(cat_findings))
                continue

            # Special formatting for reusable patterns
            if check_id == "debt.no_reuse":
                lines.extend(_group_reusable(cat_findings))
                continue

            # Default: individual checklist items
            for f in cat_findings:
                lines.append(_finding_to_checklist_item(f))
                lines.append("")

        lines.append("")

    # ── FP warnings ──
    fp_warnings = _collect_fp_warnings(report.findings)
    if fp_warnings:
        lines.append("---")
        lines.append("")
        lines.append("## ⚠️ Possible false positives")
        lines.append("")
        lines.append("The scanner uses static analysis and may flag valid code. "
                     "Check these before blindly fixing:")
        lines.append("")
        for w in fp_warnings:
            lines.append(w)
        lines.append("")

    # ── Info section (collapsed) — full LLM context ──
    info_findings = [f for f in report.findings if f.severity == "info"]
    if info_findings:
        lines.append("---")
        lines.append("")
        lines.append("<details>")
        lines.append(f"<summary>ℹ️ Info ({len(info_findings)} items)</summary>")
        lines.append("")
        for f in info_findings:
            # Show full message for LLM Context Summary
            if "LLM Context" in f.title or "Context Summary" in f.title:
                lines.append(f"### {f.title}")
                lines.append("")
                lines.append(f.message if f.message else "")
                lines.append("")
            else:
                lines.append(
                    f"- **{f.title}**: "
                    f"{f.message if f.message else ''}"
                )
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # ── Footer with AI instructions ──
    lines.append("---")
    lines.append("")
    lines.append("## How to use this report with AI")
    lines.append("")
    lines.append("Paste this file to Claude/Cursor and say:")
    lines.append("```")
    lines.append('Fix the issues in this health report, starting from HIGH severity.')
    lines.append('Skip items marked as possible false positives.')
    lines.append("```")
    lines.append("")
    lines.append("---")

    # Footer with scanned repo + fartrun links
    scanned_url = _get_git_remote_url(report.project_dir)
    footer_parts = []
    if scanned_url:
        footer_parts.append(f"Scanned: [{project_name}]({scanned_url})")
    else:
        footer_parts.append(f"Scanned: {project_name}")
    footer_parts.append(
        "Generated by [fartrun](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun)"
    )
    footer_parts.append("MCP: `npx fartrun@latest install`")
    lines.append(f"*{' · '.join(footer_parts)}*")

    return "\n".join(lines)


def save_report_md(report: HealthReport, output_path: str | None = None) -> str:
    """Generate and save MD report into .fartrun/reports/. Returns the file path."""
    md = generate_report_md(report)

    if output_path is None:
        checks_dir = Path(report.project_dir) / ".fartrun" / "reports"
        checks_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d")
        output_path = str(checks_dir / f"HEALTH-REPORT-{date}.md")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(md, encoding="utf-8")
    return output_path
