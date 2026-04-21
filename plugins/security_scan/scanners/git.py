"""Git-tracked file checks — detect committed secrets."""
from __future__ import annotations

import subprocess
from pathlib import Path

from plugins.security_scan.scanners.base import Finding


def scan_env_in_git(scan_paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in scan_paths:
        if not (path / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "ls-files"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                continue
            for tracked_file in result.stdout.strip().split("\n"):
                tracked_file = tracked_file.strip()
                if not tracked_file:
                    continue
                name = Path(tracked_file).name
                if name.startswith(".env"):
                    findings.append(Finding(
                        "config", "critical",
                        f".env file committed in git: {tracked_file}",
                        str(path / tracked_file),
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return findings
