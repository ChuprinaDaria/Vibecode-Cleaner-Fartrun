"""Tests for Port/Service Map plugin."""

from unittest.mock import patch, MagicMock
from collections import namedtuple
from plugins.port_map.collector import collect_ports

SConn = namedtuple("SConn", ["fd", "family", "type", "laddr", "raddr", "status", "pid"])
SAddr = namedtuple("SAddr", ["ip", "port"])


def _mock_process(pid, name, cwd="/home/user/project"):
    proc = MagicMock()
    proc.pid = pid
    proc.info = {"pid": pid, "name": name}
    proc.name.return_value = name
    proc.cwd.return_value = cwd
    proc.cmdline.return_value = [name]
    return proc


@patch("plugins.port_map.collector.psutil")
def test_collect_listening_ports(mock_psutil):
    mock_psutil.net_connections.return_value = [
        SConn(fd=3, family=2, type=1, laddr=SAddr("0.0.0.0", 5432), raddr=(), status="LISTEN", pid=100),
        SConn(fd=4, family=2, type=1, laddr=SAddr("127.0.0.1", 3000), raddr=(), status="LISTEN", pid=200),
    ]

    proc_100 = _mock_process(100, "postgres")
    proc_200 = _mock_process(200, "node", "/home/user/cafe")

    mock_psutil.Process.side_effect = lambda pid: {100: proc_100, 200: proc_200}[pid]
    mock_psutil.NoSuchProcess = Exception
    mock_psutil.AccessDenied = Exception

    result = collect_ports()
    assert len(result) == 2
    assert result[0]["port"] == 3000
    assert result[1]["port"] == 5432


@patch("plugins.port_map.collector.psutil")
def test_detect_port_conflict(mock_psutil):
    mock_psutil.net_connections.return_value = [
        SConn(fd=3, family=2, type=1, laddr=SAddr("0.0.0.0", 3000), raddr=(), status="LISTEN", pid=100),
        SConn(fd=4, family=2, type=1, laddr=SAddr("0.0.0.0", 3000), raddr=(), status="LISTEN", pid=200),
    ]
    proc_100 = _mock_process(100, "node", "/home/user/cafe")
    proc_200 = _mock_process(200, "node", "/home/user/nexelin")
    mock_psutil.Process.side_effect = lambda pid: {100: proc_100, 200: proc_200}[pid]
    mock_psutil.NoSuchProcess = Exception
    mock_psutil.AccessDenied = Exception

    result = collect_ports()
    conflicts = [p for p in result if p.get("conflict")]
    assert len(conflicts) >= 1


@patch("plugins.port_map.collector.psutil")
def test_project_detection_from_cwd(mock_psutil):
    mock_psutil.net_connections.return_value = [
        SConn(fd=3, family=2, type=1, laddr=SAddr("0.0.0.0", 8000), raddr=(), status="LISTEN", pid=100),
    ]
    proc = _mock_process(100, "uvicorn", "/home/dchuprina/sloth-all")
    mock_psutil.Process.side_effect = lambda pid: proc
    mock_psutil.NoSuchProcess = Exception
    mock_psutil.AccessDenied = Exception

    result = collect_ports()
    assert result[0]["project"] == "sloth-all"
