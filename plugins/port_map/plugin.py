"""Port/Service Map plugin — tracks listening ports, conflicts, services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from core.plugin import Plugin, Alert
from plugins.port_map.collector import collect_ports
from plugins.port_map.widget import PortMapWidget

if TYPE_CHECKING:
    import aiosqlite
    from textual.widget import Widget


class PortMapPlugin(Plugin):

    name = "Ports"
    icon = "🔌"

    def __init__(self, config: dict):
        self._config = config.get("plugins", {}).get("port_map", {})
        self._widget: PortMapWidget | None = None

    async def migrate(self, db: aiosqlite.Connection) -> None:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS port_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                port INTEGER NOT NULL,
                ip TEXT,
                protocol TEXT DEFAULT 'TCP',
                pid INTEGER,
                process TEXT,
                project TEXT,
                container_name TEXT,
                conflict INTEGER DEFAULT 0,
                exposed INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(port, pid)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS port_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                port INTEGER NOT NULL,
                process TEXT,
                event TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def collect(self, db: aiosqlite.Connection) -> None:
        ports = collect_ports()
        now = datetime.now(timezone.utc).isoformat()

        cursor = await db.execute("SELECT port, pid, process FROM port_services")
        old_ports = {(row[0], row[1]): row[2] for row in await cursor.fetchall()}

        await db.execute("DELETE FROM port_services")
        for p in ports:
            await db.execute("""
                INSERT INTO port_services (port, ip, protocol, pid, process, project, conflict, exposed, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["port"], p["ip"], p["protocol"], p["pid"], p["process"],
                  p.get("project", ""), int(p["conflict"]), int(p.get("exposed", False)), now))

        new_keys = {(p["port"], p["pid"]) for p in ports}
        old_keys = set(old_ports.keys())

        for key in new_keys - old_keys:
            port, pid = key
            proc = next((p["process"] for p in ports if p["port"] == port and p["pid"] == pid), "?")
            await db.execute(
                "INSERT INTO port_history (port, process, event, timestamp) VALUES (?, ?, 'up', ?)",
                (port, proc, now),
            )

        for key in old_keys - new_keys:
            port, pid = key
            proc = old_ports.get(key, "?")
            await db.execute(
                "INSERT INTO port_history (port, process, event, timestamp) VALUES (?, ?, 'down', ?)",
                (port, proc, now),
            )

        await db.commit()

        if self._widget:
            table = self._widget.query_one("#port-table", None)
            if table:
                table.update_data(ports)
            summary = self._widget.query_one("#port-summary", None)
            if summary:
                summary.update_summary(ports)

    def render(self) -> Widget:
        self._widget = PortMapWidget()
        return self._widget

    async def get_alerts(self, db: aiosqlite.Connection) -> list[Alert]:
        alerts = []
        cursor = await db.execute("SELECT port, process, project, conflict, exposed FROM port_services WHERE conflict = 1")
        for row in await cursor.fetchall():
            port, process, project, _, _ = row
            alerts.append(Alert(
                source="ports",
                severity="warning",
                title=f"Port {port} conflict",
                message=f"Port {port} used by multiple processes ({process}, project: {project})",
            ))
        return alerts
