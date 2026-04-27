"""Port and service collector using psutil."""

from __future__ import annotations

import logging
import subprocess

import psutil
from pathlib import Path

log = logging.getLogger(__name__)


def _detect_project(cwd: str) -> str:
    path = Path(cwd)
    home = Path.home()
    if str(path).startswith(str(home)):
        parts = path.relative_to(home).parts
        if parts:
            return parts[0]
    return path.name


def _collect_via_ss() -> list[dict]:
    """Fallback: parse `ss -tlnp` when psutil lacks permissions."""
    try:
        out = subprocess.check_output(
            ["ss", "-tlnp"], text=True, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    results = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[3]
        # local addr format: 0.0.0.0:8080 or [::]:8080 or *:8080
        if ":" not in local:
            continue
        ip, _, port_str = local.rpartition(":")
        try:
            port = int(port_str)
        except ValueError:
            continue
        ip = ip.strip("[]") or "0.0.0.0"

        # extract pid/process from "users:(("name",pid=123,fd=4))"
        pid = 0
        process_name = ""
        info = parts[-1] if "pid=" in parts[-1] else ""
        if "pid=" in info:
            try:
                pid = int(info.split("pid=")[1].split(",")[0].split(")")[0])
            except (ValueError, IndexError):
                pass
        if '(("' in info:
            try:
                process_name = info.split('(("')[1].split('"')[0]
            except IndexError:
                pass

        results.append({
            "port": port, "ip": ip, "protocol": "TCP",
            "pid": pid, "process": process_name,
            "project": "", "cwd": "", "conflict": False, "exposed": ip == "0.0.0.0",
        })

    # detect conflicts
    port_counts: dict[int, int] = {}
    for r in results:
        port_counts[r["port"]] = port_counts.get(r["port"], 0) + 1
    for r in results:
        r["conflict"] = port_counts[r["port"]] > 1

    results.sort(key=lambda x: x["port"])
    return results


def collect_ports() -> list[dict]:
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError) as e:
        log.warning("psutil.net_connections denied (%s), falling back to ss", e)
        return _collect_via_ss()

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
