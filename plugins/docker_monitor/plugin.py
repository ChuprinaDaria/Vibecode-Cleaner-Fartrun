"""Docker Monitor plugin — tracks containers, CPU, RAM, ports, health."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import docker

from core.plugin import Plugin, Alert
from plugins.docker_monitor.collector import collect_containers
from plugins.docker_monitor.widget import DockerMonitorWidget

if TYPE_CHECKING:
    import aiosqlite
    from textual.widget import Widget


class DockerMonitorPlugin(Plugin):

    name = "Docker"
    icon = "🐳"

    def __init__(self, config: dict):
        self._config = config.get("plugins", {}).get("docker_monitor", {})
        self._cpu_threshold = self._config.get("cpu_threshold", 80)
        self._ram_threshold = self._config.get("ram_threshold", 85)
        self._alert_on_exit = self._config.get("alert_on_exit", True)
        self._widget: DockerMonitorWidget | None = None
        try:
            self._client = docker.from_env()
        except docker.errors.DockerException:
            self._client = None

    async def migrate(self, db: aiosqlite.Connection) -> None:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS docker_containers (
                container_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                image TEXT,
                status TEXT,
                cpu_percent REAL DEFAULT 0,
                mem_usage INTEGER DEFAULT 0,
                mem_limit INTEGER DEFAULT 0,
                health TEXT,
                exit_code INTEGER DEFAULT 0,
                restart_count INTEGER DEFAULT 0,
                ports TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS docker_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id TEXT NOT NULL,
                cpu_percent REAL,
                mem_usage INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (container_id) REFERENCES docker_containers(container_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS docker_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                container_name TEXT,
                event_type TEXT,
                message TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def collect(self, db: aiosqlite.Connection) -> None:
        if not self._client:
            return

        containers = self._client.containers.list(all=True)
        infos = collect_containers(containers)
        now = datetime.now(timezone.utc).isoformat()

        for info in infos:
            c_id = info["name"]
            await db.execute("""
                INSERT INTO docker_containers
                    (container_id, name, image, status, cpu_percent, mem_usage, mem_limit, health, exit_code, restart_count, ports, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(container_id) DO UPDATE SET
                    status=excluded.status, cpu_percent=excluded.cpu_percent,
                    mem_usage=excluded.mem_usage, mem_limit=excluded.mem_limit,
                    health=excluded.health, exit_code=excluded.exit_code,
                    restart_count=excluded.restart_count, ports=excluded.ports,
                    updated_at=excluded.updated_at
            """, (
                c_id, info["name"], info["image"], info["status"],
                info["cpu_percent"], info["mem_usage"], info["mem_limit"],
                info["health"], info["exit_code"], info["restart_count"],
                str(info["ports"]), now,
            ))

            if info["status"] == "running":
                await db.execute(
                    "INSERT INTO docker_metrics (container_id, cpu_percent, mem_usage, timestamp) VALUES (?, ?, ?, ?)",
                    (c_id, info["cpu_percent"], info["mem_usage"], now),
                )

        await db.commit()
        await db.execute("DELETE FROM docker_metrics WHERE timestamp < datetime('now', '-1 day')")
        await db.commit()

        if self._widget:
            table = self._widget.query_one("#docker-table", None)
            if table:
                table.update_data(infos)

    def render(self) -> Widget:
        self._widget = DockerMonitorWidget()
        return self._widget

    async def get_alerts(self, db: aiosqlite.Connection) -> list[Alert]:
        alerts = []
        cursor = await db.execute("SELECT * FROM docker_containers")
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]

        for row in rows:
            c = dict(zip(columns, row))

            if c["status"] == "exited" and self._alert_on_exit:
                alerts.append(Alert(
                    source="docker",
                    severity="critical",
                    title=f"{c['name']} crashed (exit {c['exit_code']})",
                    message=f"Container {c['name']} exited with code {c['exit_code']}",
                ))

            if c["status"] != "running":
                continue

            if c["cpu_percent"] > self._cpu_threshold:
                alerts.append(Alert(
                    source="docker",
                    severity="warning",
                    title=f"{c['name']} CPU {c['cpu_percent']:.0f}%",
                    message=f"Container {c['name']} CPU usage at {c['cpu_percent']:.1f}% (threshold: {self._cpu_threshold}%)",
                ))

            if c["mem_limit"] > 0:
                ram_pct = (c["mem_usage"] / c["mem_limit"]) * 100
                if ram_pct > self._ram_threshold:
                    alerts.append(Alert(
                        source="docker",
                        severity="critical",
                        title=f"{c['name']} RAM {ram_pct:.0f}%",
                        message=f"Container {c['name']} RAM at {ram_pct:.1f}% (threshold: {self._ram_threshold}%)",
                        ))

            if c["health"] == "unhealthy":
                alerts.append(Alert(
                    source="docker",
                    severity="warning",
                    title=f"{c['name']} unhealthy",
                    message=f"Container {c['name']} health check is failing",
                ))

            if c["restart_count"] >= 3:
                alerts.append(Alert(
                    source="docker",
                    severity="critical",
                    title=f"{c['name']} restart loop ({c['restart_count']}x)",
                    message=f"Container {c['name']} has restarted {c['restart_count']} times",
                ))

        return alerts
