"""Tests for Docker metrics collector."""

from unittest.mock import MagicMock, patch
from plugins.docker_monitor.collector import collect_containers


def _mock_container(name, status, cpu_percent=5.0, mem_usage=100_000_000, mem_limit=500_000_000, ports=None, health="healthy", restart_count=0, exit_code=0):
    container = MagicMock()
    container.name = name
    container.status = status
    container.image.tags = ["postgres:16"]
    container.attrs = {
        "State": {
            "Health": {"Status": health} if health else {},
            "ExitCode": exit_code,
        },
        "RestartCount": restart_count,
        "Created": "2026-04-14T10:00:00Z",
        "HostConfig": {
            "Privileged": False,
            "Binds": [],
            "NetworkMode": "bridge",
        },
        "Config": {"User": "postgres"},
    }
    container.ports = ports or {"5432/tcp": [{"HostPort": "5432"}]}

    if status == "running":
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 500_000_000},
                "system_cpu_usage": 10_000_000_000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 400_000_000},
                "system_cpu_usage": 9_000_000_000,
            },
            "memory_stats": {
                "usage": mem_usage,
                "limit": mem_limit,
            },
            "networks": {
                "eth0": {"rx_bytes": 1024, "tx_bytes": 2048}
            },
        }
        container.stats.return_value = stats
    else:
        container.stats.side_effect = Exception("not running")

    return container


def test_collect_running_container():
    container = _mock_container("postgres", "running")
    result = collect_containers([container])
    assert len(result) == 1
    info = result[0]
    assert info["name"] == "postgres"
    assert info["status"] == "running"
    assert "cpu_percent" in info
    assert "mem_usage" in info
    assert info["mem_usage"] == 100_000_000


def test_collect_stopped_container():
    container = _mock_container("nginx", "exited", exit_code=137)
    result = collect_containers([container])
    assert len(result) == 1
    assert result[0]["status"] == "exited"
    assert result[0]["cpu_percent"] == 0.0


def test_collect_ports():
    container = _mock_container("web", "running", ports={"8080/tcp": [{"HostPort": "8080"}], "443/tcp": [{"HostPort": "443"}]})
    result = collect_containers([container])
    assert len(result[0]["ports"]) == 2
