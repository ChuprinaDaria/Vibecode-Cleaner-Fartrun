"""Health scan MCP tools — full project analysis for vibe coders."""
from __future__ import annotations

import mcp.types as mcp_types

from core.mcp.helpers import json_block, resolve_project_dir
from core.mcp.tools._registry import register


def _serialize_finding(f) -> dict:
    """Convert HealthFinding to dict for JSON output."""
    d = {
        "check_id": f.check_id,
        "severity": f.severity,
        "title": f.title,
        "message": f.message,
    }
    if f.details:
        # Include fix_recommendation from context7 if present
        if "fix_recommendation" in f.details:
            d["fix_recommendation"] = f.details["fix_recommendation"]
        if "context7_source" in f.details:
            d["context7_source"] = f.details["context7_source"]
    return d


def _serialize_report(report) -> dict:
    """Convert HealthReport to serializable dict."""
    findings = [_serialize_finding(f) for f in report.findings]

    # Group by severity for quick overview
    severity_counts = {}
    for f in report.findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    return {
        "project_dir": report.project_dir,
        "total_findings": len(report.findings),
        "severity_counts": severity_counts,
        "file_tree": report.file_tree,
        "entry_points": report.entry_points[:5],
        "monsters": report.monsters[:10],
        "findings": findings,
    }


@register(mcp_types.Tool(
    name="run_health_scan",
    description=(
        "Full health scan of a project: file map, dead code, tech debt, "
        "git hygiene, test coverage, framework issues, and fix recommendations "
        "from Context7 docs. Returns all findings with severity levels. "
        "Use for comprehensive project audit."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def run_health_scan(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)
    return json_block(_serialize_report(report))


@register(mcp_types.Tool(
    name="get_health_summary",
    description=(
        "Quick health check — only critical and high severity issues. "
        "Faster than full scan, shows what needs fixing NOW. "
        "Includes fix recommendations from library docs when available."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
            "include_medium": {
                "type": "boolean",
                "description": "Also include medium severity. Default false.",
            },
        },
    },
))
async def get_health_summary(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    include_medium = args.get("include_medium", False)

    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    target = {"critical", "high"}
    if include_medium:
        target.add("medium")

    important = [f for f in report.findings if f.severity in target]
    findings = [_serialize_finding(f) for f in important]

    severity_counts = {}
    for f in important:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    return json_block({
        "project_dir": project_dir,
        "total_findings": len(important),
        "total_all": len(report.findings),
        "severity_counts": severity_counts,
        "findings": findings,
    })


@register(mcp_types.Tool(
    name="get_unused_code",
    description=(
        "Find unused imports, functions, and dead code in a project. "
        "Returns only dead code findings — unused imports, unused "
        "functions/methods, orphan files, commented-out code."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_unused_code(args):
    project_dir = resolve_project_dir(args.get("project_dir"))

    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    dead_code_ids = {
        "dead.unused_imports", "dead.unused_definitions",
        "dead.orphan_files", "dead.commented_code", "dead.duplicates",
    }
    orphan_findings = [f for f in report.findings if "Orphan" in f.title]
    dead = [f for f in report.findings if f.check_id in dead_code_ids]
    dead.extend(orphan_findings)

    return json_block({
        "project_dir": project_dir,
        "unused_imports": [
            _serialize_finding(f) for f in dead
            if f.check_id == "dead.unused_imports"
        ],
        "unused_definitions": [
            _serialize_finding(f) for f in dead
            if f.check_id == "dead.unused_definitions"
        ],
        "orphan_files": [
            _serialize_finding(f) for f in dead
            if "Orphan" in f.title
        ],
        "duplicates": [
            _serialize_finding(f) for f in dead
            if f.check_id == "dead.duplicates"
        ],
        "commented_code": [
            _serialize_finding(f) for f in dead
            if f.check_id == "dead.commented_code"
        ],
        "total": len(dead),
    })


@register(mcp_types.Tool(
    name="get_tech_debt",
    description=(
        "Find tech debt: missing type hints, hardcoded values, "
        "TODO comments, error handling issues, outdated dependencies, "
        "overengineering. Returns only debt-related findings."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_tech_debt(args):
    project_dir = resolve_project_dir(args.get("project_dir"))

    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    debt_prefixes = ("debt.", "brake.overengineering")
    debt = [f for f in report.findings
            if any(f.check_id.startswith(p) for p in debt_prefixes)]

    return json_block({
        "project_dir": project_dir,
        "total": len(debt),
        "findings": [_serialize_finding(f) for f in debt],
    })


@register(mcp_types.Tool(
    name="get_security_issues",
    description=(
        "Find security issues: hardcoded secrets, insecure defaults, "
        "missing gitignore entries, framework misconfigurations. "
        "Returns only security-related findings."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_security_issues(args):
    project_dir = resolve_project_dir(args.get("project_dir"))

    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    security_ids = {
        "framework.django_secret_key", "framework.django_debug",
        "framework.django_no_throttle",
        "git.gitignore",
    }
    security_prefixes = ("framework.",)
    security = [f for f in report.findings
                if f.check_id in security_ids
                or any(f.check_id.startswith(p) for p in security_prefixes)
                or f.severity == "critical"]

    return json_block({
        "project_dir": project_dir,
        "total": len(security),
        "findings": [_serialize_finding(f) for f in security],
    })


@register(mcp_types.Tool(
    name="get_module_graph",
    description=(
        "Analyze module dependency graph: circular imports, hub modules "
        "(files imported by many others), and orphan files (unreachable from "
        "entry points). Helps understand project architecture."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_module_graph(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    module_ids = {"map.modules"}
    modules = [f for f in report.findings if f.check_id in module_ids]

    circulars = [f for f in modules if "Circular" in f.title]
    hubs = [f for f in modules if "Hub" in f.title]
    orphans = [f for f in modules if "Orphan" in f.title]

    return json_block({
        "project_dir": project_dir,
        "circular_imports": [_serialize_finding(f) for f in circulars],
        "hub_modules": [_serialize_finding(f) for f in hubs],
        "orphan_files": [_serialize_finding(f) for f in orphans],
        "total": len(modules),
    })


@register(mcp_types.Tool(
    name="get_complexity_report",
    description=(
        "Find monster files (>500 lines) and overengineered code "
        "(single-method classes, deep nesting). Shows which files "
        "need refactoring or splitting."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_complexity_report(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    ids = {"map.monsters", "brake.overengineering"}
    findings = [f for f in report.findings if f.check_id in ids]

    return json_block({
        "project_dir": project_dir,
        "monsters": [_serialize_finding(f) for f in findings
                     if f.check_id == "map.monsters"],
        "overengineering": [_serialize_finding(f) for f in findings
                           if f.check_id == "brake.overengineering"],
        "total": len(findings),
    })


@register(mcp_types.Tool(
    name="get_git_health",
    description=(
        "Git hygiene analysis: uncommitted work, commit quality, "
        "branch strategy, gitignore gaps. Shows if your git "
        "workflow needs attention."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_git_health(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    git_ids = {"git.status", "git.commits", "git.branches",
               "git.gitignore", "git.cheatsheet"}
    findings = [f for f in report.findings if f.check_id in git_ids]

    return json_block({
        "project_dir": project_dir,
        "total": len(findings),
        "findings": [_serialize_finding(f) for f in findings],
    })


@register(mcp_types.Tool(
    name="get_test_coverage",
    description=(
        "Check test health: are there tests at all, test file count, "
        "test-to-code ratio, unfinished work indicators. "
        "Zero tests = high severity finding."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_test_coverage(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    test_ids = {"brake.tests", "brake.unfinished", "brake.scope_creep"}
    findings = [f for f in report.findings if f.check_id in test_ids]

    return json_block({
        "project_dir": project_dir,
        "total": len(findings),
        "findings": [_serialize_finding(f) for f in findings],
    })


@register(mcp_types.Tool(
    name="get_docs_quality",
    description=(
        "Check documentation quality: README presence and completeness, "
        "dependency documentation, LLM context, SDK references. "
        "Shows what documentation is missing."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_docs_quality(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    doc_ids = {"docs.readme", "docs.deps", "docs.sdk_context",
               "docs.llm_context", "docs.devtools", "docs.ui_dictionary",
               "docs.dependency_docs"}
    findings = [f for f in report.findings if f.check_id in doc_ids]

    return json_block({
        "project_dir": project_dir,
        "total": len(findings),
        "findings": [_serialize_finding(f) for f in findings],
    })


@register(mcp_types.Tool(
    name="get_ui_issues",
    description=(
        "Find UI/UX issues in JSX/TSX: buttons without handlers, "
        "setState in render, missing deps arrays in useEffect, "
        "async handlers without error catching. Frontend-specific."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_ui_issues(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    ux_prefix = "ux."
    reuse_id = "debt.no_reuse"
    findings = [f for f in report.findings
                if f.check_id.startswith(ux_prefix)
                or f.check_id == reuse_id]

    return json_block({
        "project_dir": project_dir,
        "ux_issues": [_serialize_finding(f) for f in findings
                      if f.check_id.startswith(ux_prefix)],
        "reusable_patterns": [_serialize_finding(f) for f in findings
                             if f.check_id == reuse_id],
        "total": len(findings),
    })


@register(mcp_types.Tool(
    name="get_framework_check",
    description=(
        "Framework-specific issues: Django SECRET_KEY, DEBUG=True, "
        "missing throttling, cookie config. Docker latest tags, "
        "missing lockfiles, deprecated images. Heavy dirs in git."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_framework_check(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    fw_prefix = "framework."
    findings = [f for f in report.findings
                if f.check_id.startswith(fw_prefix)]

    return json_block({
        "project_dir": project_dir,
        "total": len(findings),
        "findings": [_serialize_finding(f) for f in findings],
    })


@register(mcp_types.Tool(
    name="get_outdated_deps",
    description=(
        "Check for outdated dependencies in package.json and "
        "pyproject.toml/requirements.txt. Shows current vs latest "
        "version with severity based on version gap."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_outdated_deps(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    dep_id = "debt.outdated_deps"
    findings = [f for f in report.findings if f.check_id == dep_id]

    return json_block({
        "project_dir": project_dir,
        "total": len(findings),
        "findings": [_serialize_finding(f) for f in findings],
    })


@register(mcp_types.Tool(
    name="get_config_map",
    description=(
        "Inventory of all config files: .env, Docker Compose, "
        "Dockerfiles, CI/CD workflows, Python/Node configs, "
        "build files. Shows what infrastructure exists."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
        },
    },
))
async def get_config_map(args):
    project_dir = resolve_project_dir(args.get("project_dir"))
    from core.health.project_map import run_all_checks
    report = run_all_checks(project_dir)

    config_id = "map.configs"
    config_findings = [f for f in report.findings if f.check_id == config_id]

    # Also include the configs inventory from the report
    configs_data = []
    if report.configs:
        for c in report.configs:
            if isinstance(c, dict):
                configs_data.append(c)
            else:
                configs_data.append({
                    "path": c.path,
                    "kind": c.kind,
                    "description": c.description,
                })

    return json_block({
        "project_dir": project_dir,
        "configs": configs_data,
        "findings": [_serialize_finding(f) for f in config_findings],
        "total_configs": len(configs_data),
    })


@register(mcp_types.Tool(
    name="generate_health_report",
    description=(
        "Run full health scan and generate a Markdown report file with "
        "checklist of fixes, Context7 documentation snippets, and warnings "
        "about possible false positives. Save the .md file in the project "
        "directory. Give this file to Claude to fix your project."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Absolute path to project. Defaults to CWD.",
            },
            "output_path": {
                "type": "string",
                "description": "Where to save the .md file. Default: HEALTH-REPORT-{date}.md in project root.",
            },
        },
    },
))
async def generate_health_report(args):
    from core.mcp.helpers import ok
    project_dir = resolve_project_dir(args.get("project_dir"))
    output_path = args.get("output_path")

    from core.health.project_map import run_all_checks
    from core.health.report_md import save_report_md
    report = run_all_checks(project_dir)
    saved_path = save_report_md(report, output_path)

    actionable = [f for f in report.findings if f.severity != "info"]
    return ok(
        f"Health report saved to {saved_path}\n"
        f"Total: {len(report.findings)} findings, {len(actionable)} actionable.\n"
        f"Give this file to Claude with: 'Fix the issues in HEALTH-REPORT.md'"
    )
