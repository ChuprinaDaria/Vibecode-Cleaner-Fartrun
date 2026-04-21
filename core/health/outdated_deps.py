"""Check 3.1 — Outdated Dependencies.

Parses requirements.txt / package.json, checks latest versions via
PyPI JSON API and npm registry. Caches results in SQLite for 24h.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

from core.health.models import HealthFinding, HealthReport
from core.history import HistoryDB

log = logging.getLogger(__name__)

_CACHE_HOURS = 24
_REQUEST_TIMEOUT = 5  # seconds per request


# --- Version cache in SQLite ---

def _ensure_cache_table(db: HistoryDB) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS dep_version_cache (
            package TEXT NOT NULL,
            registry TEXT NOT NULL,
            latest_version TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY (package, registry)
        )
    """)
    db.commit()


def _get_cached(db: HistoryDB, package: str, registry: str) -> str | None:
    _ensure_cache_table(db)
    cursor = db.execute(
        "SELECT latest_version, checked_at FROM dep_version_cache WHERE package = ? AND registry = ?",
        (package, registry),
    )
    row = cursor.fetchone()
    if not row:
        return None
    checked_at = datetime.fromisoformat(row[1])
    if datetime.now() - checked_at > timedelta(hours=_CACHE_HOURS):
        return None
    return row[0]


def _set_cached(db: HistoryDB, package: str, registry: str, latest: str) -> None:
    _ensure_cache_table(db)
    db.execute(
        """
        INSERT OR REPLACE INTO dep_version_cache (package, registry, latest_version, checked_at)
        VALUES (?, ?, ?, ?)
        """,
        (package, registry, latest, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()


# --- PyPI ---

def _fetch_pypi_latest(package: str) -> str | None:
    """Fetch latest version from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("info", {}).get("version")
    except (urllib.error.URLError, json.JSONDecodeError, OSError, KeyError) as e:
        log.debug("PyPI fetch failed for %s: %s", package, e)
        return None


def _get_pypi_latest(db: HistoryDB | None, package: str) -> str | None:
    if db:
        cached = _get_cached(db, package, "pypi")
        if cached:
            return cached
    latest = _fetch_pypi_latest(package)
    if latest and db:
        _set_cached(db, package, "pypi", latest)
    return latest


# --- npm ---

def _fetch_npm_latest(package: str) -> str | None:
    """Fetch latest version from npm registry."""
    url = f"https://registry.npmjs.org/{package}/latest"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("version")
    except (urllib.error.URLError, json.JSONDecodeError, OSError, KeyError) as e:
        log.debug("npm fetch failed for %s: %s", package, e)
        return None


def _get_npm_latest(db: HistoryDB | None, package: str) -> str | None:
    if db:
        cached = _get_cached(db, package, "npm")
        if cached:
            return cached
    latest = _fetch_npm_latest(package)
    if latest and db:
        _set_cached(db, package, "npm", latest)
    return latest


# --- Parse dependency files ---

def _parse_requirements_txt(path: Path) -> list[tuple[str, str]]:
    """Parse requirements.txt, return [(package, version)]."""
    deps = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Match: package==1.0.0 or package>=1.0.0 or package~=1.0
            match = re.match(r"^([a-zA-Z0-9_.-]+)\s*([=<>!~]+)\s*([a-zA-Z0-9._*-]+)", line)
            if match:
                deps.append((match.group(1).strip(), match.group(3).strip()))
            else:
                # Package without version pin
                pkg = re.match(r"^([a-zA-Z0-9_.-]+)", line)
                if pkg:
                    deps.append((pkg.group(1).strip(), ""))
    except OSError:
        pass
    return deps


def _parse_package_json(path: Path) -> list[tuple[str, str]]:
    """Parse package.json dependencies, return [(package, version)]."""
    deps = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        for section in ["dependencies", "devDependencies"]:
            for pkg, ver in data.get(section, {}).items():
                # Strip ^, ~, >= prefixes
                clean_ver = re.sub(r"^[\^~>=<]+", "", ver)
                deps.append((pkg, clean_ver))
    except (OSError, json.JSONDecodeError):
        pass
    return deps


# --- Version comparison ---

def _parse_version(ver: str) -> tuple:
    """Parse version string into comparable tuple."""
    parts = []
    for p in ver.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            # Handle pre-release like "1.0.0rc1" — just compare as string
            parts.append(p)
    return tuple(parts)


def _is_outdated(current: str, latest: str) -> bool:
    """Check if current version is older than latest."""
    if not current or not latest:
        return False
    try:
        return _parse_version(current) < _parse_version(latest)
    except (TypeError, ValueError):
        return current != latest


# --- Main check ---

def run_outdated_deps_check(
    report: HealthReport,
    project_dir: str,
    db: HistoryDB | None = None,
) -> None:
    """Check 3.1 — find outdated dependencies."""
    root = Path(project_dir)
    outdated: list[dict] = []

    # Python deps
    for req_path in [root / "requirements.txt", root / "requirements-dev.txt"]:
        if req_path.exists():
            deps = _parse_requirements_txt(req_path)
            for pkg, current_ver in deps[:30]:  # cap at 30 to avoid API spam
                latest = _get_pypi_latest(db, pkg)
                if latest and current_ver and _is_outdated(current_ver, latest):
                    outdated.append({
                        "package": pkg,
                        "current": current_ver,
                        "latest": latest,
                        "registry": "pypi",
                    })

    # JS deps
    pkg_json = root / "package.json"
    if pkg_json.exists():
        deps = _parse_package_json(pkg_json)
        for pkg, current_ver in deps[:30]:
            latest = _get_npm_latest(db, pkg)
            if latest and current_ver and _is_outdated(current_ver, latest):
                outdated.append({
                    "package": pkg,
                    "current": current_ver,
                    "latest": latest,
                    "registry": "npm",
                })

    # Generate findings
    for dep in outdated[:20]:  # cap findings
        # Determine severity by version gap
        severity = "low"
        try:
            cur = _parse_version(dep["current"])
            lat = _parse_version(dep["latest"])
            if isinstance(cur[0], int) and isinstance(lat[0], int):
                if cur[0] < lat[0]:
                    severity = "high"  # major version behind
                elif len(cur) > 1 and len(lat) > 1 and cur[1] < lat[1]:
                    severity = "medium"  # minor version behind
        except (IndexError, TypeError):
            pass

        report.findings.append(HealthFinding(
            check_id="debt.outdated_deps",
            title=f"{dep['package']} {dep['current']} \u2192 {dep['latest']}",
            severity=severity,
            message=(
                f"{dep['package']} {dep['current']} \u2192 {dep['latest']} ({dep['registry']}). "
                f"The longer you wait, the more will break when you update."
            ),
        ))

    if not outdated:
        # Check if we found any deps at all
        has_deps = (root / "requirements.txt").exists() or pkg_json.exists()
        if has_deps:
            report.findings.append(HealthFinding(
                check_id="debt.outdated_deps",
                title="Dependencies up to date",
                severity="info",
                message="All checked dependencies are on latest versions.",
            ))
