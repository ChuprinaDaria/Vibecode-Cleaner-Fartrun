"""Security scan of a repository before installing as MCP/Skill."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class RepoScanResult:
    safe: bool
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def scan_repo(repo_path: Path) -> RepoScanResult:
    """Scan a cloned repo for security issues before install."""
    warnings: list[str] = []
    blockers: list[str] = []

    # Check package.json postinstall scripts
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            scripts = data.get("scripts", {})
            for hook in ("postinstall", "preinstall", "prepare"):
                val = scripts.get(hook, "")
                for bad in ("curl", "wget", "| sh", "| bash", "child_process", "net.connect"):
                    if bad in val:
                        blockers.append(f"npm {hook} script contains '{bad}': {val[:100]}")
        except (json.JSONDecodeError, OSError):
            warnings.append("Cannot parse package.json")

    # Binary files
    suspicious_extensions = {".exe", ".dll", ".so", ".dylib", ".bin"}
    for f in repo_path.rglob("*"):
        if f.suffix.lower() in suspicious_extensions:
            warnings.append(f"Binary file: {f.relative_to(repo_path)}")

    # Obfuscated JS
    for f in repo_path.rglob("*.js"):
        if "node_modules" in f.parts:
            continue
        try:
            content = f.read_text(errors="replace")
            if len(content) > 1000 and content.count("\n") < 5:
                warnings.append(f"Possibly obfuscated JS: {f.relative_to(repo_path)}")
        except OSError:
            pass

    # Typosquatting (use existing scanner if available)
    try:
        from plugins.security_scan.scanners import (
            _KNOWN_MALICIOUS_NPM, _KNOWN_MALICIOUS_PYTHON,
            _is_typosquat, _POPULAR_NPM, _POPULAR_PYTHON,
        )
        for req in repo_path.glob("requirements*.txt"):
            for line in req.read_text(errors="replace").splitlines():
                pkg = line.strip().split("=")[0].split(">")[0].split("<")[0].strip()
                if not pkg or pkg.startswith("#"):
                    continue
                if pkg.lower() in {m.lower() for m in _KNOWN_MALICIOUS_PYTHON}:
                    blockers.append(f"Known malicious Python package: {pkg}")
                elif _is_typosquat(pkg, _POPULAR_PYTHON):
                    warnings.append(f"Possible typosquat: {pkg}")
    except ImportError:
        pass

    return RepoScanResult(safe=len(blockers) == 0, warnings=warnings, blockers=blockers)
