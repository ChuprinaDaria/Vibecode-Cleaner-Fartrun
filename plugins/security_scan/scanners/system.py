"""System-level checks — firewall, SSH, updates, sudoers, PATH perms.

All checks delegate to the platform abstraction so the same scanner
runs on Linux / macOS / Windows.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.platform import get_platform
from plugins.security_scan.scanners.base import Finding


def scan_firewall() -> list[Finding]:
    """Check if firewall is active — cross-platform."""
    platform = get_platform()
    result = platform.check_firewall()
    findings: list[Finding] = []
    if not result["active"]:
        tool = result["tool"]
        details = result["details"]
        if tool == "none":
            findings.append(Finding(
                "system", "high",
                "No firewall detected — system is open to network attacks",
                "firewall",
            ))
        else:
            findings.append(Finding(
                "system", "high",
                f"Firewall ({tool}) is inactive — {details}",
                tool,
            ))
    return findings


def scan_ssh_config() -> list[Finding]:
    """Check SSH server configuration — cross-platform."""
    platform = get_platform()
    result = platform.check_ssh_config()
    findings: list[Finding] = []
    if not result["exists"]:
        return findings
    for issue in result["issues"]:
        severity = "critical" if "empty passwords" in issue else (
            "high" if "root login" in issue else "medium"
        )
        findings.append(Finding("system", severity, f"SSH: {issue}", "sshd_config"))
    return findings


def scan_system_updates() -> list[Finding]:
    """Check for available security updates — cross-platform."""
    platform = get_platform()
    updates = platform.check_system_updates()
    findings: list[Finding] = []
    for desc in updates:
        severity = "high" if "security" in desc.lower() else "medium"
        findings.append(Finding(
            "system", severity,
            f"{desc} — update your system",
            "updates",
        ))
    return findings


def scan_sudoers() -> list[Finding]:
    """Check for risky admin configurations — cross-platform."""
    platform = get_platform()
    result = platform.check_sudoers()
    findings: list[Finding] = []
    if result["nopasswd_all"]:
        findings.append(Finding(
            "system", "medium",
            "Current user has passwordless admin access for ALL commands",
            "sudoers",
        ))
    return findings


def scan_world_writable() -> list[Finding]:
    """Check for world-writable directories in PATH."""
    findings: list[Finding] = []
    sep = ";" if os.name == "nt" else ":"
    path_dirs = os.environ.get("PATH", "").split(sep)
    for d in path_dirs:
        p = Path(d)
        if not p.exists():
            continue
        try:
            mode = p.stat().st_mode & 0o777
            if mode & 0o002:
                findings.append(Finding(
                    "system", "high",
                    f"PATH directory {d} is world-writable ({oct(mode)}) — "
                    "attacker can place malicious binaries there",
                    str(p),
                ))
        except OSError:
            continue
    return findings
