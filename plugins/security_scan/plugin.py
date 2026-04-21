"""Security Scan plugin — Docker, configs, deps, network."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

log = logging.getLogger("fartrun.security_scan")

from core.plugin import Plugin, Alert
from plugins.security_scan.scanners import (
    scan_docker_security,
    scan_env_in_git,
    scan_exposed_ports,
    scan_pip_audit,
    scan_npm_audit,
    scan_sentinel_processes,
    scan_sentinel_network,
    scan_sentinel_filesystem,
    scan_sentinel_cron,
    scan_sentinel_secrets,
    scan_sentinel_autostart,
    scan_suspicious_packages,
    Finding,
)
from plugins.security_scan.widget import SecurityWidget

if TYPE_CHECKING:
    import aiosqlite
    from textual.widget import Widget


class SecurityScanPlugin(Plugin):

    name = "Security"
    icon = "🛡"

    def __init__(self, config: dict):
        self._config = config.get("plugins", {}).get("security_scan", {})
        self._scan_interval = self._config.get("scan_interval", 3600)
        raw_paths = self._config.get("scan_paths", ["~"])
        self._scan_paths = [Path(p).expanduser() for p in raw_paths]
        self._last_scan: float = 0
        self._widget: SecurityWidget | None = None

    async def migrate(self, db: aiosqlite.Connection) -> None:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS security_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                source TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS security_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                duration_seconds REAL,
                findings_count INTEGER
            )
        """)

    async def collect(self, db: aiosqlite.Connection) -> None:
        now = time.time()
        if (now - self._last_scan) < self._scan_interval and self._last_scan > 0:
            return

        start = time.time()
        all_findings: list[Finding] = []

        try:
            import docker
            client = docker.from_env()
            containers = client.containers.list(all=True)
            from plugins.docker_monitor.collector import collect_containers
            infos = collect_containers(containers)
            all_findings.extend(scan_docker_security(infos))
        except Exception as e:
            log.warning("docker security scan skipped: %s", e)

        all_findings.extend(scan_env_in_git(self._scan_paths))

        try:
            from plugins.port_map.collector import collect_ports
            ports = collect_ports()
            all_findings.extend(scan_exposed_ports(ports))
        except Exception as e:
            log.warning("exposed-ports scan skipped: %s", e)

        # Rust sentinel scanners
        all_findings.extend(scan_sentinel_processes())
        all_findings.extend(scan_sentinel_network())
        all_findings.extend(scan_sentinel_filesystem(self._scan_paths))
        all_findings.extend(scan_sentinel_cron())

        # New security guardian scanners
        all_findings.extend(scan_sentinel_secrets(self._scan_paths))
        all_findings.extend(scan_sentinel_autostart())
        all_findings.extend(scan_suspicious_packages(self._scan_paths))

        all_findings.extend(scan_pip_audit(self._scan_paths))
        all_findings.extend(scan_npm_audit(self._scan_paths))

        duration = time.time() - start
        self._last_scan = now

        await db.execute("UPDATE security_findings SET resolved_at = CURRENT_TIMESTAMP WHERE resolved_at IS NULL")

        for f in all_findings:
            await db.execute(
                "INSERT INTO security_findings (type, severity, description, source) VALUES (?, ?, ?, ?)",
                (f.type, f.severity, f.description, f.source),
            )

        await db.execute(
            "INSERT INTO security_scans (duration_seconds, findings_count) VALUES (?, ?)",
            (round(duration, 1), len(all_findings)),
        )
        await db.commit()

        if self._widget:
            findings_dicts = [{"type": f.type, "severity": f.severity, "description": f.description, "source": f.source} for f in all_findings]
            table = self._widget.query_one("#security-table", None)
            if table:
                table.update_data(findings_dicts)
            summary = self._widget.query_one("#security-summary", None)
            if summary:
                summary.update_counts(findings_dicts)

    def render(self) -> Widget:
        self._widget = SecurityWidget()
        return self._widget

    async def get_alerts(self, db: aiosqlite.Connection) -> list[Alert]:
        alerts = []
        cursor = await db.execute(
            "SELECT type, severity, description, source FROM security_findings WHERE resolved_at IS NULL"
        )
        for row in await cursor.fetchall():
            type_, severity, desc, source = row
            if severity in ("critical", "high"):
                alerts.append(Alert(
                    source="security",
                    severity=severity,
                    title=f"[{type_}] {desc[:50]}",
                    message=desc,
                ))
        return alerts
