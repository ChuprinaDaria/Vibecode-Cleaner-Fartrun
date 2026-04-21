"""Docker container metrics collector."""

from __future__ import annotations

import logging

log = logging.getLogger("fartrun.docker_collector")


def _calc_cpu_percent(stats: dict) -> float:
    cpu = stats.get("cpu_stats", {})
    precpu = stats.get("precpu_stats", {})
    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get("cpu_usage", {}).get("total_usage", 0)
    sys_delta = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    online_cpus = cpu.get("online_cpus", 1)
    if sys_delta > 0 and cpu_delta >= 0:
        return round((cpu_delta / sys_delta) * online_cpus * 100, 1)
    return 0.0


def _parse_ports(ports_dict: dict) -> list[dict]:
    result = []
    if not ports_dict:
        return result
    for container_port_proto, bindings in ports_dict.items():
        if not bindings:
            continue
        parts = container_port_proto.split("/")
        container_port = parts[0]
        protocol = parts[1] if len(parts) > 1 else "tcp"
        for binding in bindings:
            result.append({
                "container_port": container_port,
                "host_port": binding.get("HostPort", ""),
                "protocol": protocol,
            })
    return result


def collect_containers(containers: list) -> list[dict]:
    results = []
    for c in containers:
        state = c.attrs.get("State", {})
        health_obj = state.get("Health", {})
        health = health_obj.get("Status") if health_obj else None

        info = {
            "name": c.name,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else "unknown",
            "created": c.attrs.get("Created", ""),
            "health": health,
            "exit_code": state.get("ExitCode", 0),
            "restart_count": c.attrs.get("RestartCount", 0),
            "ports": _parse_ports(c.ports),
            "cpu_percent": 0.0,
            "mem_usage": 0,
            "mem_limit": 0,
            "net_rx": 0,
            "net_tx": 0,
            "privileged": c.attrs.get("HostConfig", {}).get("Privileged", False),
            "binds": c.attrs.get("HostConfig", {}).get("Binds") or [],
            "network_mode": c.attrs.get("HostConfig", {}).get("NetworkMode", ""),
            "user": c.attrs.get("Config", {}).get("User", ""),
        }

        if c.status == "running":
            try:
                stats = c.stats(stream=False)
                info["cpu_percent"] = _calc_cpu_percent(stats)
                mem = stats.get("memory_stats", {})
                info["mem_usage"] = mem.get("usage", 0)
                info["mem_limit"] = mem.get("limit", 0)
                networks = stats.get("networks", {})
                for iface_stats in networks.values():
                    info["net_rx"] += iface_stats.get("rx_bytes", 0)
                    info["net_tx"] += iface_stats.get("tx_bytes", 0)
            except Exception as e:
                log.warning("docker stats for %s skipped: %s", info.get("name", "?"), e)

        results.append(info)
    return results
