"""Detects which test framework a project uses, returns a default command.

Priority: pyproject.toml > Cargo.toml > package.json > heuristic.
The caller is responsible for honoring an explicit override from config.toml.
"""
from __future__ import annotations

import json
from pathlib import Path


def _has_pytest_marker(project_dir: Path) -> bool:
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(errors="ignore")
        if "[tool.pytest" in text or "pytest" in text:
            return True
    if (project_dir / "setup.cfg").exists():
        if "pytest" in (project_dir / "setup.cfg").read_text(errors="ignore"):
            return True
    if (project_dir / "tox.ini").exists():
        if "pytest" in (project_dir / "tox.ini").read_text(errors="ignore"):
            return True
    if (project_dir / "tests" / "conftest.py").exists():
        return True
    if (project_dir / "conftest.py").exists():
        return True
    return False


def _read_npm_test_script(project_dir: Path) -> str | None:
    pkg = project_dir / "package.json"
    if not pkg.exists():
        return None
    try:
        data = json.loads(pkg.read_text(errors="ignore"))
    except json.JSONDecodeError:
        return None
    scripts = data.get("scripts") or {}
    return scripts.get("test")


def detect_framework(project_dir: Path) -> tuple[str, list[str]]:
    """Return (framework_name, default argv).

    Empty argv means 'no framework detected — caller must show an error
    or ask user to set [tests] command override'.
    """
    project_dir = Path(project_dir)

    if _has_pytest_marker(project_dir):
        cmd = ["pytest", "--tb=short"]
        # Ignore common fixture/sample directories that may contain
        # intentionally-failing tests (test data for parsers, etc.)
        fixtures_dir = project_dir / "tests" / "fixtures"
        if fixtures_dir.is_dir():
            cmd.append(f"--ignore={fixtures_dir}")
        return ("pytest", cmd)

    if (project_dir / "Cargo.toml").exists():
        return ("cargo", ["cargo", "test", "--all-features"])

    npm_test = _read_npm_test_script(project_dir)
    if npm_test is not None:
        if "vitest" in npm_test:
            return ("vitest", ["npm", "test", "--", "--reporter=json"])
        if "jest" in npm_test:
            return ("jest", ["npm", "test", "--", "--json"])
        return ("generic", ["npm", "test"])

    return ("generic", [])
