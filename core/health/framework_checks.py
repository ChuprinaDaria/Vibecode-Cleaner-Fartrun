"""Framework & infra checks — Django security, Docker best practices, frontend bundle bloat."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.health.models import HealthFinding, HealthReport
from core.health import _SKIP_DIRS

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Django Security
# ---------------------------------------------------------------------------

def _find_django_settings(root: Path) -> Path | None:
    """Find Django settings.py (max 3 levels deep, skip venvs)."""
    for depth, parent in enumerate(_walk_dirs(root, max_depth=3)):
        candidate = parent / "settings.py"
        if candidate.exists():
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
                if "INSTALLED_APPS" in text or "SECRET_KEY" in text:
                    return candidate
            except OSError:
                pass
    return None


def _walk_dirs(root: Path, max_depth: int, _depth: int = 0):
    """Yield directories up to max_depth, skipping _SKIP_DIRS."""
    yield root
    if _depth >= max_depth:
        return
    try:
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name not in _SKIP_DIRS:
                yield from _walk_dirs(child, max_depth, _depth + 1)
    except (PermissionError, OSError):
        pass


def check_django_security(report: HealthReport, project_dir: str) -> None:
    """Check Django settings for common security misconfigurations."""
    root = Path(project_dir)
    settings_path = _find_django_settings(root)
    if not settings_path:
        return

    try:
        text = settings_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    rel = str(settings_path.relative_to(root))

    # 1. Hardcoded SECRET_KEY or insecure default
    # Distinguish: direct hardcoded string (critical) vs env-loaded with bad default (medium)
    _env_loaded = re.search(
        r"""SECRET_KEY\s*=\s*(?:config|env|os\.environ|os\.getenv)\s*\(""", text,
    )
    _hardcoded = re.search(r"""SECRET_KEY\s*=\s*['"](?!%\()""", text)
    _insecure_default = re.search(r"""default\s*=\s*['"]django-insecure-""", text)

    if _hardcoded and not _env_loaded:
        report.findings.append(HealthFinding(
            check_id="framework.django_secret_key",
            title=f"Hardcoded SECRET_KEY in {rel}",
            severity="critical",
            message=(
                f"{rel} has a hardcoded SECRET_KEY — not loaded from env. "
                f"Anyone with this key can forge sessions, CSRF tokens, and signed cookies. "
                f"Generate a new one: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\" "
                f"and put it in an env var with NO default fallback."
            ),
        ))
    elif _env_loaded and _insecure_default:
        report.findings.append(HealthFinding(
            check_id="framework.django_secret_key",
            title=f"Insecure SECRET_KEY default in {rel}",
            severity="medium",
            message=(
                f"{rel} loads SECRET_KEY from env but falls back to 'django-insecure-...' default. "
                f"If .env is missing on production, anyone can forge sessions. "
                f"Remove the default or make it crash without the env var."
            ),
        ))

    # 2. DEBUG = True as default
    debug_default = re.search(
        r"""DEBUG\s*=\s*(?:config\s*\([^)]*default\s*=\s*True|True)""", text
    )
    if debug_default:
        report.findings.append(HealthFinding(
            check_id="framework.django_debug",
            title=f"DEBUG defaults to True in {rel}",
            severity="high",
            message=(
                f"{rel}: DEBUG defaults to True. If .env is missing on production, "
                f"Django will show full tracebacks with source code, local variables, and settings to anyone. "
                f"Set default=False and only enable DEBUG explicitly in dev."
            ),
        ))

    # 3. SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE always True conflicts with DEBUG
    if debug_default:
        secure_always = (
            re.search(r"SESSION_COOKIE_SECURE\s*=\s*True", text)
            and not re.search(r"SESSION_COOKIE_SECURE\s*=.*DEBUG", text, re.IGNORECASE)
        )
        if secure_always:
            report.findings.append(HealthFinding(
                check_id="framework.django_cookie_config",
                title=f"Secure cookies conflict with DEBUG in {rel}",
                severity="medium",
                message=(
                    f"{rel}: SESSION_COOKIE_SECURE=True is hardcoded, but DEBUG can be True. "
                    f"On localhost without HTTPS, admin login won't work — cookies won't be sent. "
                    f"Tie it to DEBUG: SESSION_COOKIE_SECURE = not DEBUG."
                ),
            ))

    # 4. No rate limiting / throttle in REST_FRAMEWORK
    if "rest_framework" in text:
        if "THROTTLE" not in text.upper() and "throttle" not in text:
            report.findings.append(HealthFinding(
                check_id="framework.django_no_throttle",
                title=f"No API throttling configured in {rel}",
                severity="medium",
                message=(
                    f"{rel}: REST_FRAMEWORK has no DEFAULT_THROTTLE_CLASSES. "
                    f"Any endpoint (contact forms, auth) can be hammered by bots. "
                    f"Add: 'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'], "
                    f"'DEFAULT_THROTTLE_RATES': {{'anon': '20/hour'}}."
                ),
            ))


# ---------------------------------------------------------------------------
# Docker Best Practices
# ---------------------------------------------------------------------------

def check_docker_best_practices(report: HealthReport, project_dir: str) -> None:
    """Check Docker/docker-compose files for common issues."""
    root = Path(project_dir)

    # Find all docker-compose files
    compose_files = list(root.glob("docker-compose*.yml")) + list(root.glob("docker-compose*.yaml"))

    for compose_file in compose_files:
        try:
            text = compose_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel = compose_file.name

        # 1. Deprecated 'version' field
        if re.search(r"^version\s*:", text, re.MULTILINE):
            report.findings.append(HealthFinding(
                check_id="framework.docker_version_deprecated",
                title=f"Deprecated 'version' in {rel}",
                severity="low",
                message=(
                    f"{rel}: 'version' field is deprecated in Docker Compose v2+. "
                    f"Remove it — Docker ignores it anyway."
                ),
            ))

        # 2. :latest tags in production compose files
        if "prod" in rel or "production" in rel:
            latest_matches = re.findall(r"image:\s*\S+:latest", text)
            if latest_matches:
                report.findings.append(HealthFinding(
                    check_id="framework.docker_latest_tag",
                    title=f"':latest' tags in {rel}",
                    severity="medium",
                    message=(
                        f"{rel}: using ':latest' image tags in production. "
                        f"No way to rollback, no way to know what's deployed. "
                        f"Pin versions: image: myapp:v1.2.3 or use commit SHA tags."
                    ),
                ))

    # Find Dockerfiles
    dockerfiles = list(root.glob("**/Dockerfile*"))
    dockerfiles = [d for d in dockerfiles if not any(skip in str(d) for skip in _SKIP_DIRS)]

    for dockerfile in dockerfiles:
        try:
            text = dockerfile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel = str(dockerfile.relative_to(root))

        # 3. npm install without lockfile
        if "npm install" in text and "package-lock" not in text and "COPY package-lock" not in text:
            # Check if lockfile is actually copied
            if not re.search(r"COPY\s+.*lock", text):
                report.findings.append(HealthFinding(
                    check_id="framework.docker_no_lockfile",
                    title=f"npm install without lockfile in {rel}",
                    severity="medium",
                    message=(
                        f"{rel}: runs 'npm install' but doesn't copy package-lock.json. "
                        f"Builds are not reproducible — you'll get different versions each time. "
                        f"COPY package-lock.json and use 'npm ci' instead of 'npm install'."
                    ),
                ))

    # 4. venv / node_modules tracked in git
    _check_heavy_dirs_in_git(report, root)


def _check_heavy_dirs_in_git(report: HealthReport, root: Path) -> None:
    """Detect if venv/node_modules are tracked by git."""
    from core.health.git_utils import run_git as _run_git

    heavy_dirs = ["venv", ".venv", "env", "node_modules"]
    for name in heavy_dirs:
        # Check if directory exists and is tracked by git
        for match in root.rglob(name):
            if not match.is_dir():
                continue
            # Skip if inside another skip dir
            if any(part in _SKIP_DIRS for part in match.parts[:-1]):
                continue
            # Check if git tracks any files in this dir
            rel_dir = str(match.relative_to(root))
            tracked = _run_git(str(root), "ls-files", rel_dir, "--error-unmatch")
            if tracked is not None and tracked.strip():
                report.findings.append(HealthFinding(
                    check_id="framework.heavy_dir_in_git",
                    title=f"{rel_dir}/ is tracked by git",
                    severity="high",
                    message=(
                        f"{rel_dir}/ contains {len(tracked.splitlines())} tracked files. "
                        f"This is a dependency directory — it should be in .gitignore, not in git. "
                        f"Fix: echo '{name}/' >> .gitignore && git rm -r --cached {rel_dir}"
                    ),
                ))
                break  # one finding per dir name is enough


# ---------------------------------------------------------------------------
# Frontend Bundle Bloat
# ---------------------------------------------------------------------------

def check_frontend_bundle_bloat(report: HealthReport, project_dir: str) -> None:
    """Detect import * patterns that bloat frontend bundles."""
    root = Path(project_dir)

    # Find JS/JSX/TS/TSX files (skip node_modules, dist, build, venv)
    source_files: list[Path] = []
    for ext in ("*.js", "*.jsx", "*.ts", "*.tsx"):
        for f in root.rglob(ext):
            if any(part in _SKIP_DIRS or part in ("dist", "build", "coverage") for part in f.parts):
                continue
            source_files.append(f)

    wildcard_imports: list[tuple[str, str]] = []

    for src in source_files:
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Match: import * as Foo from 'bar'
        for match in re.finditer(r"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]", text):
            alias, module = match.group(1), match.group(2)
            # Only flag icon libs and known-heavy packages
            heavy_packages = ("react-icons", "lodash", "@mui/icons", "@fortawesome", "heroicons")
            if any(pkg in module for pkg in heavy_packages):
                rel = str(src.relative_to(root))
                wildcard_imports.append((rel, module))

    if wildcard_imports:
        files_str = ", ".join(f"{f} ({m})" for f, m in wildcard_imports[:5])
        report.findings.append(HealthFinding(
            check_id="framework.frontend_wildcard_import",
            title=f"import * from heavy packages in {len(wildcard_imports)} files",
            severity="medium",
            message=(
                f"Wildcard imports pull entire libraries into the bundle: {files_str}. "
                f"Import only what you use: import {{ FaBook }} from 'react-icons/fa' "
                f"instead of import * as ReactIcons from 'react-icons/fa'."
            ),
        ))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_framework_checks(report: HealthReport, project_dir: str) -> None:
    """Run all framework & infra checks."""
    check_django_security(report, project_dir)
    check_docker_best_practices(report, project_dir)
    check_frontend_bundle_bloat(report, project_dir)
