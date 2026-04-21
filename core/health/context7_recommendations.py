"""Phase 9 — Context7 fix recommendations.

After scanning, enrich findings with real documentation snippets from
Context7 MCP. Runs context7 as subprocess (stdio MCP), queries library
docs relevant to each finding, and appends fix_recommendation to
finding.details.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess

from core.health.models import HealthFinding, HealthReport
from core.stack_detector import detect_stack

log = logging.getLogger(__name__)

# Map check_id → [(library_name, query_topic)]
_FINDING_TO_QUERY: dict[str, list[tuple[str, str]]] = {
    # --- framework ---
    "framework.django_secret_key": [
        ("Django", "SECRET_KEY configuration security best practices environment variable"),
    ],
    "framework.django_debug": [
        ("Django", "DEBUG setting production deployment security configuration"),
    ],
    "framework.django_cookie_config": [
        ("Django", "SESSION_COOKIE_SECURE CSRF_COOKIE_SECURE HTTPS cookies security"),
    ],
    "framework.django_no_throttle": [
        ("Django REST Framework", "throttling rate limiting DEFAULT_THROTTLE_CLASSES setup"),
    ],
    "framework.docker_version_deprecated": [
        ("Docker", "Compose version field deprecated compose specification"),
    ],
    "framework.docker_latest_tag": [
        ("Docker", "Dockerfile FROM tag pinning avoid latest best practices"),
    ],
    "framework.docker_no_lockfile": [
        ("Docker", "npm ci package-lock.json Dockerfile best practices reproducible builds"),
    ],
    "framework.heavy_dir_in_git": [
        ("Git", "gitignore node_modules vendor large directories best practices"),
    ],
    "framework.frontend_wildcard_import": [
        ("JavaScript", "tree shaking named imports avoid wildcard import performance"),
    ],
    # --- brake system ---
    "brake.tests": [
        ("pytest", "getting started writing first test basic example"),
    ],
    "brake.unfinished": [
        ("Python", "TODO FIXME tracking code completion best practices"),
    ],
    "brake.scope_creep": [
        ("Python", "project structure module organization separation of concerns"),
    ],
    "brake.overengineering": [
        ("Python", "YAGNI simple code avoid overengineering premature abstraction"),
    ],
    "brake.opensource_check": [
        ("Python", "LICENSE file open source project setup MIT Apache"),
    ],
    # --- tech debt ---
    "debt.no_types": [
        ("Python", "type hints annotations mypy getting started"),
        ("TypeScript", "TypeScript strict mode type checking configuration"),
    ],
    "debt.error_handling": [
        ("Python", "exception handling bare except best practices try except"),
    ],
    "debt.hardcoded": [
        ("Python", "environment variables configuration secrets management python-dotenv"),
    ],
    "debt.todos": [
        ("Python", "TODO FIXME code quality tracking technical debt"),
    ],
    "debt.outdated_deps": [
        ("pip", "pip install upgrade outdated packages requirements"),
        ("npm", "npm outdated update packages dependencies"),
    ],
    "debt.no_reuse": [
        ("Python", "code reuse DRY principle refactoring duplicate code functions"),
    ],
    # --- dead code ---
    "dead.unused_imports": [
        ("Python", "unused imports autoflake isort cleanup linting"),
    ],
    "dead.unused_definitions": [
        ("Python", "dead code detection vulture unused functions classes"),
    ],
    "dead.orphan_files": [
        ("Python", "project structure unused files cleanup organization"),
    ],
    "dead.commented_code": [
        ("Python", "commented out code cleanup version control best practices"),
    ],
    "dead.duplicates": [
        ("Python", "duplicate code detection refactoring DRY extract function"),
    ],
    # --- git ---
    "git.status": [
        ("Git", "git status unstaged uncommitted changes workflow best practices"),
    ],
    "git.commits": [
        ("Git", "commit messages conventional commits best practices frequency"),
    ],
    "git.branches": [
        ("Git", "branch management stale branches cleanup git branch delete"),
    ],
    "git.gitignore": [
        ("Git", "gitignore patterns templates Python Node.js best practices"),
    ],
    "git.cheatsheet": [
        ("Git", "git commands cheat sheet common operations workflow"),
    ],
    # --- docs ---
    "docs.readme": [
        ("Python", "README.md writing good documentation project setup instructions"),
    ],
    "docs.deps": [
        ("pip", "requirements.txt pyproject.toml dependency management"),
        ("npm", "package.json dependencies devDependencies management"),
    ],
    "docs.devtools": [
        ("Python", "development tools linting formatting black ruff flake8 setup"),
    ],
    "docs.llm_context": [
        ("Python", "CLAUDE.md AGENTS.md LLM context project documentation AI"),
    ],
    "docs.ui_dictionary": [
        ("Python", "UI component naming conventions design system documentation"),
    ],
    "docs.sdk_context": [
        ("Python", "SDK API documentation context setup instructions"),
    ],
    # --- UI/UX ---
    "uiux.qss_slop": [
        ("Qt", "QSS stylesheet best practices consistent styling PyQt"),
    ],
    "uiux.qss_quality": [
        ("Qt", "QSS stylesheet quality color consistency font management"),
    ],
    "uiux.stylelint": [
        ("Stylelint", "CSS linting configuration rules setup getting started"),
    ],
    "uiux.lighthouse": [
        ("Lighthouse", "web performance audit accessibility SEO best practices"),
    ],
    "uiux.pa11y": [
        ("Pa11y", "accessibility testing automated WCAG compliance"),
    ],
    # --- map ---
    "map.monsters": [
        ("Python", "large files refactoring splitting modules code organization"),
    ],
    "map.modules": [
        ("Python", "module structure circular imports package organization __init__"),
    ],
}

# check_id prefix → fallback library to query
_PREFIX_FALLBACK: dict[str, str] = {
    "framework.django": "Django",
    "framework.docker": "Docker",
    "framework.frontend": "JavaScript",
    "debt.": "Python",
    "dead.": "Python",
    "git.": "Git",
    "docs.": "Python",
    "brake.": "Python",
    "uiux.": "CSS",
    "map.": "Python",
}

# Enrich critical, high AND medium
_ENRICH_SEVERITIES = {"critical", "high", "medium"}


def _npx_path() -> str | None:
    return shutil.which("npx")


def _run_context7_session(messages: list[dict], timeout: int = 15) -> list[dict]:
    """Send multiple JSON-RPC messages to context7 MCP via stdio."""
    import os
    if os.environ.get("FARTRUN_NO_CONTEXT7"):
        return []
    npx = _npx_path()
    if not npx:
        return []

    # MCP protocol: initialize first, then tool calls
    init_msg = {
        "jsonrpc": "2.0", "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "fartrun-health", "version": "1.0"},
        },
    }
    all_messages = [init_msg] + messages
    stdin_text = "\n".join(json.dumps(m) for m in all_messages) + "\n"

    try:
        result = subprocess.run(
            [npx, "-y", "@upstash/context7-mcp"],
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            log.debug("context7 process failed: %s", result.stderr[:200])
            return []

        responses = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return responses
    except (subprocess.TimeoutExpired, OSError) as e:
        log.debug("context7 session error: %s", e)
        return []


def _resolve_and_query(library: str, topic: str) -> str | None:
    """Resolve library ID and fetch docs in a single context7 session."""
    # Step 1: resolve library ID
    resolve_msg = {
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {
            "name": "resolve-library-id",
            "arguments": {
                "libraryName": library,
                "query": topic,
            },
        },
    }
    responses = _run_context7_session([resolve_msg], timeout=10)

    # Find resolve response (id=1)
    library_id = None
    for resp in responses:
        if resp.get("id") == 1 and "result" in resp:
            result = resp["result"]
            # MCP tools/call returns {"content": [{"text": "..."}]}
            if isinstance(result, dict) and "content" in result:
                for item in result["content"]:
                    if isinstance(item, dict) and "text" in item:
                        text = item["text"]
                        # Parse the response to find library ID
                        # It typically contains lines like "/org/project"
                        for line in text.split("\n"):
                            line = line.strip()
                            if line.startswith("/") and "/" in line[1:]:
                                library_id = line.split()[0] if " " in line else line
                                break
                        if not library_id and "/" in text:
                            # Try to extract from text
                            for word in text.split():
                                if word.startswith("/") and word.count("/") >= 2:
                                    library_id = word.rstrip(".,;)")
                                    break
            break

    if not library_id:
        log.debug("context7: could not resolve library ID for %s", library)
        return None

    # Step 2: query docs with resolved ID
    query_msg = {
        "jsonrpc": "2.0", "id": 2,
        "method": "tools/call",
        "params": {
            "name": "query-docs",
            "arguments": {
                "libraryId": library_id,
                "query": topic,
            },
        },
    }
    responses = _run_context7_session([query_msg], timeout=15)

    for resp in responses:
        if resp.get("id") == 2 and "result" in resp:
            result = resp["result"]
            if isinstance(result, dict) and "content" in result:
                texts = []
                for item in result["content"]:
                    if isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])
                if texts:
                    return "\n".join(texts)
    return None


def _auto_query_for_finding(
    finding: HealthFinding,
    project_libs: set[str],
) -> list[tuple[str, str]]:
    """Build context7 query from finding metadata when no explicit mapping exists."""
    # Determine library from check_id prefix
    lib = None
    for prefix, fallback_lib in _PREFIX_FALLBACK.items():
        if finding.check_id.startswith(prefix):
            lib = fallback_lib
            break

    # Try to pick a more specific lib from the project stack
    check_lower = finding.check_id.lower()
    title_lower = finding.title.lower()
    combined = f"{check_lower} {title_lower}"

    stack_hints = {
        "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
        "react": "React", "vue": "Vue", "next": "Next.js",
        "express": "Express", "docker": "Docker", "pytest": "pytest",
        "sqlalchemy": "SQLAlchemy", "celery": "Celery",
        "pydantic": "Pydantic", "alembic": "Alembic",
        "tailwind": "Tailwind CSS", "typescript": "TypeScript",
        "node": "Node.js", "npm": "npm", "pip": "pip",
    }
    for keyword, lib_name in stack_hints.items():
        if keyword in combined or keyword in project_libs:
            lib = lib_name
            break

    if not lib:
        return []

    # Build query from finding title + message keywords
    topic = f"{finding.title} {finding.check_id.replace('.', ' ')} best practices"
    return [(lib, topic)]


_MAX_ENRICHMENTS = 10  # max context7 queries per scan


def enrich_findings_with_context7(
    report: HealthReport,
    project_dir: str,
    severities: set[str] | None = None,
) -> None:
    """Enrich report findings with context7 documentation recommendations."""
    target_severities = severities or _ENRICH_SEVERITIES

    if not _npx_path():
        log.debug("npx not available, skipping context7 enrichment")
        return

    # Detect project libraries
    stack = detect_stack(project_dir)
    project_libs = {lib.name.lower() for lib in stack}

    # Always-available libraries (not project-specific)
    universal_libs = {
        "python", "docker", "pytest", "git", "css", "javascript",
        "django", "django rest framework", "pip", "npm",
        "node.js", "typescript", "qt",
    }

    # Prioritize: critical first, then high, then medium
    priority_order = {"critical": 0, "high": 1, "medium": 2}
    candidates = [
        f for f in report.findings
        if f.severity in target_severities
        and not f.details.get("fix_recommendation")
    ]
    candidates.sort(key=lambda f: priority_order.get(f.severity, 9))

    enriched_count = 0
    for finding in candidates:
        if enriched_count >= _MAX_ENRICHMENTS:
            break

        # Explicit mapping first, then auto-fallback
        queries = _FINDING_TO_QUERY.get(finding.check_id)
        if not queries:
            queries = _auto_query_for_finding(finding, project_libs)
        if not queries:
            continue

        for lib_name, topic in queries:
            # Check if library is relevant to this project
            if lib_name.lower() not in project_libs and lib_name.lower() not in universal_libs:
                continue

            docs = _resolve_and_query(lib_name, topic)
            if not docs:
                continue

            # Trim to reasonable size
            snippet = docs[:800].strip()
            if len(docs) > 800:
                snippet += "\n..."

            finding.details["fix_recommendation"] = snippet
            finding.details["context7_source"] = lib_name
            enriched_count += 1
            break

    if enriched_count:
        log.info("context7: enriched %d findings with documentation", enriched_count)
