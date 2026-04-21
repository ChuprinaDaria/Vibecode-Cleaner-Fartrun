"""Docker container security checks."""
from __future__ import annotations

from plugins.security_scan.scanners.base import Finding


def scan_docker_security(container_infos: list[dict]) -> list[Finding]:
    findings: list[Finding] = []
    for c in container_infos:
        name = c["name"]

        if c.get("privileged"):
            findings.append(Finding("docker", "critical", f"{name}: runs in privileged mode", name))

        for bind in c.get("binds") or []:
            if "docker.sock" in bind:
                findings.append(Finding("docker", "critical", f"{name}: docker.sock mounted inside container", name))

        if c.get("network_mode") == "host":
            findings.append(Finding("docker", "high", f"{name}: uses host network mode", name))

        if not c.get("user"):
            findings.append(Finding("docker", "high", f"{name}: runs as root (no USER set)", name))

        image = c.get("image", "")
        if image.endswith(":latest") or ":" not in image:
            findings.append(Finding("docker", "medium", f"{name}: uses :latest tag ({image})", name))

    return findings
