"""Tests for security scanners."""

from pathlib import Path
from unittest.mock import patch, MagicMock
from plugins.security_scan.scanners import (
    scan_docker_security,
    scan_env_in_git,
    scan_exposed_ports,
    Finding,
)


def test_finding_creation():
    f = Finding(type="docker", severity="critical", description="Container runs as root", source="postgres")
    assert f.severity == "critical"
    assert f.source == "postgres"


def test_docker_privileged_detection():
    container_info = {
        "name": "risky", "privileged": True, "binds": [],
        "network_mode": "bridge", "user": "", "image": "app:latest",
    }
    findings = scan_docker_security([container_info])
    privs = [f for f in findings if "privileged" in f.description.lower()]
    assert len(privs) == 1
    assert privs[0].severity == "critical"


def test_docker_socket_mounted():
    container_info = {
        "name": "dind", "privileged": False,
        "binds": ["/var/run/docker.sock:/var/run/docker.sock"],
        "network_mode": "bridge", "user": "", "image": "app:latest",
    }
    findings = scan_docker_security([container_info])
    socket_findings = [f for f in findings if "docker.sock" in f.description.lower()]
    assert len(socket_findings) == 1


def test_docker_root_user():
    container_info = {
        "name": "rootapp", "privileged": False, "binds": [],
        "network_mode": "bridge", "user": "", "image": "app:latest",
    }
    findings = scan_docker_security([container_info])
    root_findings = [f for f in findings if "runs as root" in f.description.lower()]
    assert len(root_findings) == 1
    assert root_findings[0].severity == "high"


def test_docker_latest_tag():
    container_info = {
        "name": "unstable", "privileged": False, "binds": [],
        "network_mode": "bridge", "user": "app", "image": "redis:latest",
    }
    findings = scan_docker_security([container_info])
    latest_findings = [f for f in findings if ":latest" in f.description]
    assert len(latest_findings) == 1
    assert latest_findings[0].severity == "medium"


def test_env_in_git(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=password123")

    with patch("plugins.security_scan.scanners.git.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(
            returncode=0, stdout=".env\nconfig/.env.prod\n",
        )
        mock_sub.TimeoutExpired = Exception
        findings = scan_env_in_git([tmp_path])
        assert len(findings) >= 1
        assert findings[0].severity == "critical"


def test_exposed_ports():
    ports = [
        {"port": 5432, "ip": "0.0.0.0", "process": "postgres", "project": ""},
        {"port": 3000, "ip": "127.0.0.1", "process": "node", "project": "cafe"},
    ]
    findings = scan_exposed_ports(ports)
    assert len(findings) == 1
    assert "0.0.0.0" in findings[0].description
