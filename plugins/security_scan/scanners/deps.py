"""Vulnerable-dependency scanners — pip-audit + npm audit."""
from __future__ import annotations

import subprocess
from pathlib import Path

from plugins.security_scan.scanners.base import Finding, json_loads


def scan_pip_audit(scan_paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in scan_paths:
        for req_file in path.rglob("requirements*.txt"):
            try:
                result = subprocess.run(
                    ["pip-audit", "-r", str(req_file), "--format", "json", "--progress-spinner", "off"],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    continue
                try:
                    data = json_loads(result.stdout)
                    for vuln in data.get("dependencies", []):
                        for v in vuln.get("vulns", []):
                            severity = "critical" if "critical" in v.get("fix_versions", [""])[0].lower() else "high"
                            findings.append(Finding(
                                "deps", severity,
                                f"{vuln['name']}=={vuln['version']}: {v.get('id', 'CVE-?')} — {v.get('description', '')[:100]}",
                                str(req_file),
                            ))
                except (ValueError, KeyError):
                    pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
    return findings


def scan_npm_audit(scan_paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in scan_paths:
        for pkg_file in path.rglob("package.json"):
            pkg_dir = pkg_file.parent
            if not (pkg_dir / "node_modules").exists():
                continue
            try:
                result = subprocess.run(
                    ["npm", "audit", "--json"],
                    capture_output=True, text=True, timeout=60, cwd=str(pkg_dir),
                )
                try:
                    data = json_loads(result.stdout)
                    vulns = data.get("vulnerabilities", {})
                    for name, info in vulns.items():
                        sev = info.get("severity", "moderate")
                        severity_map = {"critical": "critical", "high": "high", "moderate": "medium", "low": "low"}
                        findings.append(Finding(
                            "deps", severity_map.get(sev, "medium"),
                            f"npm: {name} — {sev} severity",
                            str(pkg_dir),
                        ))
                except (ValueError, KeyError):
                    pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
    return findings
