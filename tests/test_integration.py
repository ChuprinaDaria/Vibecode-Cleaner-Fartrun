"""Integration test — app creates, registers plugins, runs migrations."""

import pytest
from pathlib import Path
from core.config import load_config, DEFAULTS
from core.sqlite_db import Database
from core.alerts import AlertManager
from plugins.docker_monitor.plugin import DockerMonitorPlugin
from plugins.port_map.plugin import PortMapPlugin
from plugins.security_scan.plugin import SecurityScanPlugin


@pytest.mark.asyncio
async def test_all_plugins_migrate(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.connect()

    plugins = [
        DockerMonitorPlugin(DEFAULTS),
        PortMapPlugin(DEFAULTS),
        SecurityScanPlugin(DEFAULTS),
    ]

    for plugin in plugins:
        await db.run_migration(plugin.migrate)

    async with db.connection() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in await cursor.fetchall()]

    await db.close()

    expected = [
        "docker_containers", "docker_events", "docker_metrics",
        "port_history", "port_services",
        "security_findings", "security_scans",
    ]
    for t in expected:
        assert t in tables, f"Missing table: {t}"


def test_all_plugins_render():
    plugins = [
        DockerMonitorPlugin(DEFAULTS),
        PortMapPlugin(DEFAULTS),
        SecurityScanPlugin(DEFAULTS),
    ]
    for plugin in plugins:
        widget = plugin.render()
        assert widget is not None


def test_alert_manager_processes_plugin_alerts():
    from core.plugin import Alert
    manager = AlertManager(DEFAULTS)

    alert = Alert(source="docker", severity="critical", title="test crash", message="container died")
    assert manager.process(alert) is True
    assert manager.process(alert) is False
