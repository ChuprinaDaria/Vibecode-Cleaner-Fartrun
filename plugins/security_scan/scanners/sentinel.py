"""Rust-powered sentinel scanners — fast, cross-platform host IDS.

Each scanner is a no-op when the optional ``sentinel`` package isn't
installed, so importing this module is always safe.
"""
from __future__ import annotations

from pathlib import Path

from plugins.security_scan.scanners.base import Finding, sentinel_available

if sentinel_available:
    import sentinel  # noqa: F401  — actual usage gated below


def scan_sentinel_processes() -> list[Finding]:
    """Detect cryptominers, reverse shells, suspicious processes."""
    if not sentinel_available:
        return []
    return [
        Finding("process", pf.severity, pf.description, f"pid:{pf.pid}")
        for pf in sentinel.scan_processes()
    ]


def scan_sentinel_network() -> list[Finding]:
    """Detect suspicious ESTABLISHED connections (C2, Tor, IRC, mining)."""
    if not sentinel_available:
        return []
    return [
        Finding("network", nf.severity, nf.description, nf.remote_addr)
        for nf in sentinel.scan_network()
    ]


def scan_sentinel_filesystem(scan_paths: list[Path]) -> list[Finding]:
    """Single-pass FS scan: permissions, malware paths, SUID, /tmp execs."""
    if not sentinel_available:
        return []
    path_strs = [str(p) for p in scan_paths]
    return [
        Finding("filesystem", ff.severity, ff.description, ff.path)
        for ff in sentinel.scan_filesystem(path_strs)
    ]


def scan_sentinel_cron() -> list[Finding]:
    """Audit crontab, systemd timers, launchd, Task Scheduler."""
    if not sentinel_available:
        return []
    return [
        Finding("cron", cf.severity, cf.description, cf.source)
        for cf in sentinel.scan_scheduled_tasks()
    ]


def scan_sentinel_secrets(scan_paths: list[Path]) -> list[Finding]:
    """Detect hardcoded API keys, tokens, passwords in source files."""
    if not sentinel_available:
        return []
    path_strs = [str(p) for p in scan_paths]
    return [
        Finding("secrets", sf.severity, sf.description, sf.path)
        for sf in sentinel.scan_secrets(path_strs)
    ]


def scan_sentinel_autostart() -> list[Finding]:
    """Detect persistence in shell RC, systemd, XDG autostart."""
    if not sentinel_available:
        return []
    return [
        Finding("autostart", af.severity, af.description, af.path)
        for af in sentinel.scan_autostart()
    ]


def scan_container_escape() -> list[Finding]:
    """Detect container escape vectors — CAP_SYS_ADMIN, docker.sock."""
    if not sentinel_available:
        return []
    findings = []
    for f in sentinel.scan_container_escape():
        if f.severity == "info":
            continue  # skip informational "running inside container"
        findings.append(Finding("container", f.severity, f.description, f.evidence))
    return findings


def scan_supply_chain(scan_paths: list[Path]) -> list[Finding]:
    """Scan lock files for supply chain attack indicators."""
    if not sentinel_available:
        return []
    path_strs = [str(p) for p in scan_paths]
    return [
        Finding("packages", f.severity, f.description, f.path)
        for f in sentinel.scan_supply_chain(path_strs)
    ]


def scan_git_hooks(scan_paths: list[Path]) -> list[Finding]:
    """Audit git hooks for suspicious scripts."""
    if not sentinel_available:
        return []
    path_strs = [str(p) for p in scan_paths]
    return [
        Finding("config", f.severity, f.description, f.path)
        for f in sentinel.scan_git_hooks(path_strs)
    ]


def scan_env_leaks() -> list[Finding]:
    """Detect API keys and tokens in process environment variables."""
    if not sentinel_available:
        return []
    return [
        Finding("secrets", f.severity, f.description, f.process)
        for f in sentinel.scan_env_leaks()
    ]
