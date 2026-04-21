"""Suspicious-package scanner — typosquatting + known malicious lists.

Reads requirements*.txt, pyproject.toml, package.json under each
scan path and flags packages that look like a typo of a popular
name or appear in a curated malicious-name set.
"""
from __future__ import annotations

from pathlib import Path

from plugins.security_scan.scanners.base import Finding, json_loads

_POPULAR_PYTHON = [
    "requests", "django", "flask", "numpy", "pandas", "tensorflow", "pytorch",
    "boto3", "pillow", "cryptography", "paramiko", "sqlalchemy", "celery",
    "redis", "psycopg2", "aiohttp", "fastapi", "pydantic", "scrapy",
    "beautifulsoup4", "selenium", "matplotlib", "scipy", "scikit-learn",
    "httpx", "uvicorn", "gunicorn", "alembic", "black", "mypy", "pytest",
    "setuptools", "pip", "wheel", "docker", "kubernetes", "anthropic",
    "openai", "langchain", "transformers", "torch", "pyyaml", "jinja2",
    "click", "attrs", "marshmallow", "arrow", "pendulum", "rich",
    "typer", "loguru", "tenacity",
]

_POPULAR_NPM = [
    "react", "express", "lodash", "axios", "webpack", "next", "vue",
    "angular", "typescript", "eslint", "prettier", "jest", "mocha",
    "chalk", "commander", "dotenv", "cors", "mongoose", "sequelize",
    "prisma", "socket.io", "tailwindcss", "vite", "esbuild", "rollup",
    "postcss", "sass", "nodemon", "babel", "webpack-cli",
]

_KNOWN_MALICIOUS_PYTHON: set[str] = {
    "colourama", "python-binance", "python3-dateutil", "jeIlyfish",
    "python-mongo", "pymongodb", "requesocks", "requesrs", "python-ftp",
    "beautifulsup4", "djanga", "djnago", "numppy", "pandaas",
    "urlib3", "urllib", "flaskk",
}

_KNOWN_MALICIOUS_NPM: set[str] = {
    "crossenv", "cross-env.js", "d3.js", "fabric-js", "ffmepg",
    "gruntcli", "http-proxy.js", "jquery.js", "mariadb", "mongose",
    "mssql.js", "mssql-node", "mysqljs", "nodecaffe", "nodefabric",
    "nodeffmpeg", "nodemailer-js", "nodemssql", "node-openssl",
    "noderequest", "nodesass", "nodesqlite", "node-tkinter",
    "opencv.js", "openssl.js", "proxy.js", "shadowsock", "smb",
    "sqlite.js", "sqliter", "sqlserver",
}

_SUSPICIOUS_SCRIPT_PATTERNS = [
    "curl", "wget", "eval", "exec", "child_process",
    "http.get", "net.connect",
]


def _levenshtein(s1: str, s2: str) -> int:
    """Simple Levenshtein distance, no external deps."""
    if s1 == s2:
        return 0
    len1, len2 = len(s1), len(s2)
    if len1 == 0:
        return len2
    if len2 == 0:
        return len1
    prev = list(range(len2 + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i]
        for j, c2 in enumerate(s2, 1):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[len2]


def _is_typosquat(name: str, popular: list[str]) -> bool:
    """Return True if name is suspiciously close to a popular package but not equal."""
    if len(name) <= 3:
        return False
    name_lower = name.lower()
    for pkg in popular:
        if name_lower == pkg.lower():
            return False
        if _levenshtein(name_lower, pkg.lower()) <= 2:
            return True
    return False


def scan_suspicious_packages(scan_paths: list[Path]) -> list[Finding]:
    """Scan for known malicious packages and typosquatting attempts."""
    findings: list[Finding] = []

    for base_path in scan_paths:
        # --- requirements*.txt ---
        for req_file in base_path.rglob("requirements*.txt"):
            try:
                content = req_file.read_text(errors="replace")
            except OSError:
                continue
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # strip version specifiers: requests>=2.0,<3 → requests
                pkg_name = line.split("=")[0].split(">")[0].split("<")[0].split("[")[0].strip()
                if not pkg_name:
                    continue
                pkg_lower = pkg_name.lower()
                if pkg_lower in {m.lower() for m in _KNOWN_MALICIOUS_PYTHON}:
                    findings.append(Finding(
                        "packages", "critical",
                        f"Known malicious Python package: {pkg_name}",
                        str(req_file),
                    ))
                elif _is_typosquat(pkg_name, _POPULAR_PYTHON):
                    findings.append(Finding(
                        "packages", "high",
                        f"Possible typosquat of a popular Python package: {pkg_name}",
                        str(req_file),
                    ))

        # --- pyproject.toml ---
        for toml_file in base_path.rglob("pyproject.toml"):
            try:
                content = toml_file.read_text(errors="replace")
            except OSError:
                continue
            in_deps = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("[") and "dependencies" in stripped.lower():
                    in_deps = True
                    continue
                if stripped.startswith("[") and in_deps:
                    in_deps = False
                if not in_deps or not stripped or stripped.startswith("#"):
                    continue
                # grab package name: 'requests = "^2.0"' or '"requests"'
                pkg_name = stripped.split("=")[0].strip().strip('"').strip("'")
                if not pkg_name or pkg_name.startswith("["):
                    continue
                pkg_lower = pkg_name.lower()
                if pkg_lower in {m.lower() for m in _KNOWN_MALICIOUS_PYTHON}:
                    findings.append(Finding(
                        "packages", "critical",
                        f"Known malicious Python package: {pkg_name}",
                        str(toml_file),
                    ))
                elif _is_typosquat(pkg_name, _POPULAR_PYTHON):
                    findings.append(Finding(
                        "packages", "high",
                        f"Possible typosquat of a popular Python package: {pkg_name}",
                        str(toml_file),
                    ))

        # --- package.json ---
        for pkg_file in base_path.rglob("package.json"):
            # skip node_modules
            if "node_modules" in pkg_file.parts:
                continue
            try:
                data = json_loads(pkg_file.read_bytes())
            except (OSError, ValueError):
                continue

            # check lifecycle scripts for suspicious commands
            scripts = data.get("scripts", {})
            for script_name in ("postinstall", "preinstall", "prepare"):
                script_val = scripts.get(script_name, "")
                if not script_val:
                    continue
                for pattern in _SUSPICIOUS_SCRIPT_PATTERNS:
                    if pattern in script_val:
                        findings.append(Finding(
                            "packages", "critical",
                            f"Suspicious npm {script_name} script uses '{pattern}': {script_val[:120]}",
                            str(pkg_file),
                        ))
                        break  # one finding per script is enough

            # check dependency names
            all_deps: dict = {}
            all_deps.update(data.get("dependencies", {}))
            all_deps.update(data.get("devDependencies", {}))
            for pkg_name in all_deps:
                pkg_lower = pkg_name.lower()
                if pkg_lower in {m.lower() for m in _KNOWN_MALICIOUS_NPM}:
                    findings.append(Finding(
                        "packages", "critical",
                        f"Known malicious npm package: {pkg_name}",
                        str(pkg_file),
                    ))
                elif _is_typosquat(pkg_name, _POPULAR_NPM):
                    findings.append(Finding(
                        "packages", "high",
                        f"Possible typosquat of a popular npm package: {pkg_name}",
                        str(pkg_file),
                    ))

    return findings
