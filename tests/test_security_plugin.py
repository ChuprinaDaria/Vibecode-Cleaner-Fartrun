"""Tests for Security Scan plugin."""

import pytest
import aiosqlite
from plugins.security_scan.plugin import SecurityScanPlugin
from core.config import DEFAULTS


@pytest.fixture
def plugin():
    return SecurityScanPlugin(DEFAULTS)


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
        assert "security_findings" in tables
        assert "security_scans" in tables


@pytest.mark.asyncio
async def test_store_and_retrieve_findings(plugin, tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as conn:
        await plugin.migrate(conn)
        await conn.commit()

        await conn.execute(
            "INSERT INTO security_findings (type, severity, description, source) VALUES (?, ?, ?, ?)",
            ("docker", "critical", "Container runs privileged", "postgres"),
        )
        await conn.commit()

        alerts = await plugin.get_alerts(conn)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"


@pytest.mark.asyncio
async def test_findings_severity_counts(plugin, tmp_path):
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as conn:
        await plugin.migrate(conn)
        await conn.commit()

        for sev in ["critical", "critical", "high", "medium", "low", "low", "low"]:
            await conn.execute(
                "INSERT INTO security_findings (type, severity, description, source) VALUES (?, ?, ?, ?)",
                ("test", sev, f"Test {sev} finding", "test"),
            )
        await conn.commit()

        cursor = await conn.execute(
            "SELECT severity, COUNT(*) FROM security_findings GROUP BY severity"
        )
        counts = dict(await cursor.fetchall())
        assert counts["critical"] == 2
        assert counts["high"] == 1
        assert counts["low"] == 3
