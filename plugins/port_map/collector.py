"""Port and service collector using psutil."""

from __future__ import annotations

import psutil
from pathlib import Path


def _detect_project(cwd: str) -> str:
    path = Path(cwd)
    home = Path.home()
    if str(path).startswith(str(home)):
        parts = path.relative_to(home).parts
        if parts:
            return parts[0]
    return path.name


def collect_ports() -> list[dict]:
    connections = psutil.net_connections(kind="inet")
    listening = [c for c in connections if c.status == "LISTEN" and c.pid]

    port_pids: dict[int, list] = {}
    for conn in listening:
        port = conn.laddr.port
        port_pids.setdefault(port, []).append(conn)

    results = []
    seen = set()

    for conn in listening:
        port = conn.laddr.port
        pid = conn.pid
        key = (port, pid)
        if key in seen:
            continue
        seen.add(key)

        ip = conn.laddr.ip
        protocol = "TCP" if conn.type == 1 else "UDP"

        process_name = ""
        project = ""
        cwd = ""
        try:
            proc = psutil.Process(pid)
            process_name = proc.name()
            cwd = proc.cwd()
            project = _detect_project(cwd)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        has_conflict = len(port_pids.get(port, [])) > 1

        results.append({
            "port": port,
            "ip": ip,
            "protocol": protocol,
            "pid": pid,
            "process": process_name,
            "project": project,
            "cwd": cwd,
            "conflict": has_conflict,
            "exposed": ip == "0.0.0.0",
        })

    results.sort(key=lambda x: x["port"])
    return results
