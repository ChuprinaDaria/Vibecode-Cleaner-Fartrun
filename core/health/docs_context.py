"""Docs & Context checks — README quality, dependency docs, DevTools tips, LLM context."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.health.models import HealthFinding, HealthReport

log = logging.getLogger(__name__)


_README_EXTS = {"", ".md", ".mdx", ".rst", ".txt", ".adoc"}


def _find_readme(project_dir: str) -> Path | None:
    """Return the project-root README file if present, matching case-insensitively.

    Accepts `README`, `README.md`, `README.MD`, `Readme.md`, `readme`,
    `README.rst`, `README.mdx`, `README.adoc`, etc. Only the top-level
    directory is scanned — a README inside `docs/` is not the project README.
    """
    root = Path(project_dir)
    try:
        entries = list(root.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.is_file():
            continue
        if entry.stem.lower() != "readme":
            continue
        if entry.suffix.lower() in _README_EXTS:
            return entry
    return None


def check_readme(report: HealthReport, project_dir: str) -> None:
    """Check 6.1 — README existence and quality."""
    readme = _find_readme(project_dir)

    if not readme:
        report.findings.append(HealthFinding(
            check_id="docs.readme",
            title="No README file",
            severity="medium",
            message=(
                "No README. In a month you won't remember how to run this. "
                "Write 5 lines: what it is, how to install, how to run."
            ),
        ))
        return

    try:
        content = readme.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    lines = content.strip().splitlines()
    word_count = len(content.split())

    missing = []

    content_lower = content.lower()
    if not any(kw in content_lower for kw in ["install", "setup", "getting started", "встановлення"]):
        missing.append("installation instructions")
    if not any(kw in content_lower for kw in ["run", "start", "usage", "запуск", "використання"]):
        missing.append("how to run")
    if word_count < 20:
        missing.append("meaningful description (too short)")

    if missing:
        report.findings.append(HealthFinding(
            check_id="docs.readme",
            title=f"README incomplete: missing {', '.join(missing[:2])}",
            severity="low",
            message=(
                f"README exists ({len(lines)} lines) but missing: {', '.join(missing)}. "
                f"A good README has: what this is, how to install, how to run."
            ),
        ))
    else:
        report.findings.append(HealthFinding(
            check_id="docs.readme",
            title=f"README: {len(lines)} lines",
            severity="info",
            message=f"README looks complete ({word_count} words). Has install and run instructions.",
        ))


def check_dependency_docs(report: HealthReport, project_dir: str) -> None:
    """Check 6.2 — are dependency files up to date with actual imports."""
    root = Path(project_dir)

    # Python: check requirements.txt vs actual imports
    req_file = root / "requirements.txt"
    if req_file.exists():
        try:
            req_content = req_file.read_text(encoding="utf-8", errors="replace")
            req_packages = set()
            for line in req_content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    pkg = re.split(r"[=<>!~\[]", line)[0].strip().lower().replace("-", "_")
                    if pkg:
                        req_packages.add(pkg)

            # Scan Python imports
            used_imports = set()
            for py_file in root.rglob("*.py"):
                rel = str(py_file.relative_to(root))
                if any(skip in rel for skip in ["node_modules", ".venv", "venv", "__pycache__", "test"]):
                    continue
                try:
                    code = py_file.read_text(encoding="utf-8", errors="replace")
                    for match in re.finditer(r"^(?:import|from)\s+(\w+)", code, re.MULTILINE):
                        mod = match.group(1).lower().replace("-", "_")
                        if mod not in _PYTHON_STDLIB:
                            used_imports.add(mod)
                except OSError:
                    continue

            in_req_not_code = req_packages - used_imports - {"pip", "setuptools", "wheel"}

            if in_req_not_code:
                extras = sorted(in_req_not_code)[:5]
                report.findings.append(HealthFinding(
                    check_id="docs.deps",
                    title=f"Unused in requirements.txt: {', '.join(extras[:3])}",
                    severity="low",
                    message=(
                        f"In requirements.txt but not imported: {', '.join(extras)}. "
                        f"Either remove them or you forgot to use them."
                    ),
                ))

        except OSError:
            pass

    # Check package.json exists if JS files present
    from core.health import has_files_with_ext
    has_js = has_files_with_ext(root, "js") or has_files_with_ext(root, "ts")
    pkg_json = root / "package.json"
    if has_js and not pkg_json.exists():
        report.findings.append(HealthFinding(
            check_id="docs.deps",
            title="JS/TS files but no package.json",
            severity="low",
            message="You have JavaScript/TypeScript files but no package.json. Dependencies aren't documented.",
        ))


def check_devtools_tips(report: HealthReport, project_dir: str) -> None:
    """Check 6.4 — show DevTools tips for frontend projects."""
    root = Path(project_dir)

    from core.health import has_files_with_ext
    is_frontend = (
        has_files_with_ext(root, "jsx")
        or has_files_with_ext(root, "tsx")
        or has_files_with_ext(root, "vue")
        or has_files_with_ext(root, "svelte")
        or (root / "next.config.js").exists()
        or (root / "next.config.mjs").exists()
        or (root / "vite.config.js").exists()
        or (root / "vite.config.ts").exists()
    )

    if is_frontend:
        report.findings.append(HealthFinding(
            check_id="docs.devtools",
            title="Frontend project \u2014 use DevTools",
            severity="info",
            message=(
                "Can't explain to AI which button to change? "
                "F12 \u2192 click element \u2192 copy HTML and CSS \u2192 show AI. It'll understand."
            ),
        ))


def generate_llm_context(report: HealthReport, project_dir: str) -> None:
    """Check 6.5 — generate a concise project summary for LLM context."""
    root = Path(project_dir)

    parts = []
    parts.append(f"# Project: {root.name}")
    parts.append("")

    # Stack detection
    stack = []
    from core.health import has_files_with_ext
    if has_files_with_ext(root, "py"):
        stack.append("Python")
        if (root / "manage.py").exists():
            stack.append("Django")
    if has_files_with_ext(root, "js") or has_files_with_ext(root, "ts"):
        stack.append("JavaScript/TypeScript")
        if has_files_with_ext(root, "jsx") or has_files_with_ext(root, "tsx"):
            stack.append("React")
        if has_files_with_ext(root, "vue"):
            stack.append("Vue")
    if (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
        stack.append("Docker")

    if stack:
        parts.append(f"**Stack:** {', '.join(stack)}")
        parts.append("")

    # File stats from report
    if report.file_tree:
        ft = report.file_tree
        parts.append(f"**Size:** {ft.get('total_files', '?')} files, {ft.get('total_dirs', '?')} dirs")

    # Entry points from report
    if report.entry_points:
        parts.append("")
        parts.append("**Entry points:**")
        for ep in report.entry_points[:5]:
            parts.append(f"- `{ep['path']}` \u2014 {ep['description']}")

    # Hub modules from report
    if report.module_map and report.module_map.get("hub_modules"):
        parts.append("")
        parts.append("**Key modules:**")
        for path, count in report.module_map["hub_modules"][:5]:
            parts.append(f"- `{path}` (imported by {count} files)")

    # Configs from report
    if report.configs:
        parts.append("")
        parts.append("**Config files:**")
        for c in report.configs[:5]:
            parts.append(f"- `{c['path']}` \u2014 {c['description']}")

    context_text = "\n".join(parts)

    report.findings.append(HealthFinding(
        check_id="docs.llm_context",
        title="LLM Context Summary",
        severity="info",
        message=(
            "Copy this to give AI context about your project:\n"
            + context_text
        ),
        details={"context": context_text},
    ))


def check_ui_vocabulary(report: HealthReport, project_dir: str) -> None:
    """Check 6.6 — UI vocabulary reference for frontend projects."""
    root = Path(project_dir)

    from core.health import has_files_with_ext
    is_frontend = (
        has_files_with_ext(root, "jsx")
        or has_files_with_ext(root, "tsx")
        or has_files_with_ext(root, "vue")
        or has_files_with_ext(root, "svelte")
        or has_files_with_ext(root, "html")
    )

    if is_frontend:
        report.findings.append(HealthFinding(
            check_id="docs.ui_dictionary",
            title="UI Element Dictionary available",
            severity="info",
            message=(
                "Frontend project detected. Can't explain to AI which button to change? "
                "Open the UI Dictionary — 20 elements with names, pictures, and example prompts."
            ),
            details={"has_ui_dictionary": True},
        ))


def check_unknown_packages(report: HealthReport, project_dir: str) -> None:
    """Check 6.7 — detect packages AI might not know."""
    try:
        from core.context_fetcher import ContextFetcher
        fetcher = ContextFetcher(project_dir)
        unknown = fetcher.detect_unknown_packages()
        if unknown:
            names = [f"{p.name} ({p.registry})" for p in unknown[:5]]
            more = f" (+{len(unknown) - 5} more)" if len(unknown) > 5 else ""
            report.findings.append(HealthFinding(
                check_id="docs.sdk_context",
                title=f"Unknown packages: {', '.join(n.split(' ')[0] for n in names[:3])}",
                severity="info",
                message=(
                    f"AI might not know these packages: {', '.join(names)}{more}. "
                    f"Fetch their docs so AI understands your stack."
                ),
                details={"unknown_packages": [
                    {"name": p.name, "version": p.version, "registry": p.registry}
                    for p in unknown
                ]},
            ))
    except Exception as e:
        log.debug("Unknown packages check error: %s", e)


def run_docs_context_checks(report: HealthReport, project_dir: str) -> None:
    """Run all docs & context checks."""
    check_readme(report, project_dir)
    check_dependency_docs(report, project_dir)
    check_devtools_tips(report, project_dir)
    check_ui_vocabulary(report, project_dir)
    check_unknown_packages(report, project_dir)
    generate_llm_context(report, project_dir)


# Common Python stdlib modules
_PYTHON_STDLIB = {
    "os", "sys", "re", "json", "math", "time", "datetime", "collections",
    "itertools", "functools", "pathlib", "typing", "dataclasses", "enum",
    "abc", "io", "hashlib", "hmac", "secrets", "uuid", "random",
    "copy", "pprint", "textwrap", "string", "struct", "codecs",
    "csv", "configparser", "tomllib", "argparse", "getopt",
    "logging", "warnings", "traceback",
    "threading", "multiprocessing", "subprocess", "asyncio", "concurrent",
    "socket", "http", "urllib", "email", "html", "xml",
    "sqlite3", "dbm",
    "unittest", "doctest", "pdb",
    "shutil", "glob", "fnmatch", "tempfile", "stat",
    "gzip", "bz2", "lzma", "zipfile", "tarfile",
    "ctypes", "platform", "sysconfig", "site",
    "importlib", "pkgutil", "inspect", "dis",
    "contextlib", "operator", "weakref",
    "decimal", "fractions", "statistics",
    "array", "queue", "heapq", "bisect",
    "pydoc", "webbrowser",
    "signal", "mmap", "select", "selectors",
    "base64", "binascii",
    "__future__", "builtins", "types",
}
