"""Tests for Docker Monitor plugin."""

import pytest
import aiosqlite
from plugins.docker_monitor.plugin import DockerMonitorPlugin
from core.config import DEFAULTS


@pytest.fixture
def plugin():
    return DockerMonitorPlugin(DEFAULTS)


@pytest.mark.asyncio
async def test_migrate_creates_tables(plugin, tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as conn:
        await plugin.migrate(conn)
        await conn.commit()

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        assert "docker_containers" in tables
        assert "docker_metrics" in tables
        assert "docker_events" in tables


@pytest.mark.asyncio
async def test_get_alerts_cpu_threshold(plugin, tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as conn:
        await plugin.migrate(conn)
        await conn.commit()

        await conn.execute(
            "INSERT INTO docker_containers (container_id, name, status, cpu_percent, mem_usage, mem_limit, image) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("abc123", "worker", "running", 95.0, 500_000_000, 1_000_000_000, "app:latest"),
        )
        await conn.commit()

        alerts = await plugin.get_alerts(conn)
        cpu_alerts = [a for a in alerts if "CPU" in a.title]
        assert len(cpu_alerts) == 1
        assert cpu_alerts[0].severity == "warning"


@pytest.mark.asyncio
async def test_get_alerts_container_exited(plugin, tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as conn:
        await plugin.migrate(conn)
        await conn.commit()

        await conn.execute(
            "INSERT INTO docker_containers (container_id, name, status, cpu_percent, mem_usage, mem_limit, image, exit_code) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("def456", "nginx", "exited", 0, 0, 0, "nginx:latest", 137),
        )
        await conn.commit()

        alerts = await plugin.get_alerts(conn)
        exit_alerts = [a for a in alerts if "exited" in a.title.lower() or "crashed" in a.title.lower()]
        assert len(exit_alerts) >= 1
        assert exit_alerts[0].severity == "critical"
