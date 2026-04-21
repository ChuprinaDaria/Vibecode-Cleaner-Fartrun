"""Network exposure checks — listening ports."""
from __future__ import annotations

from plugins.security_scan.scanners.base import Finding


def scan_exposed_ports(ports: list[dict]) -> list[Finding]:
    findings: list[Finding] = []
    for p in ports:
        if p["ip"] == "0.0.0.0":
            findings.append(Finding(
                "network", "high",
                f"Port {p['port']} ({p['process']}) exposed on 0.0.0.0 instead of 127.0.0.1",
                f"port:{p['port']}",
            ))
    return findings
