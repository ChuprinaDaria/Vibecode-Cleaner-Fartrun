"""Port Map TUI widget."""

from __future__ import annotations

from textual.widgets import DataTable, Static
from textual.containers import Vertical


class PortTable(DataTable):
    def on_mount(self) -> None:
        self.add_columns("PORT", "PROTO", "PROCESS", "CONTAINER", "PROJECT", "STATUS")
        self.cursor_type = "row"

    def update_data(self, ports: list[dict], docker_ports: dict[int, str] | None = None) -> None:
        docker_ports = docker_ports or {}
        self.clear()
        for p in ports:
            port = str(p["port"])
            container = docker_ports.get(p["port"], "—")

            if p["conflict"]:
                status = "[red]CONFLICT[/]"
                port = f"[red]⚠ {port}[/]"
            else:
                status = "[green]● UP[/]"

            self.add_row(port, p["protocol"], p["process"], container, p.get("project", ""), status)


class PortSummary(Static):
    def update_summary(self, ports: list[dict]) -> None:
        total = len(ports)
        conflicts = sum(1 for p in ports if p["conflict"])
        exposed = sum(1 for p in ports if p.get("exposed"))
        self.update(f"{total} ports listening | {conflicts} conflicts | {exposed} exposed (0.0.0.0)")


class PortMapWidget(Vertical):
    def compose(self):
        yield PortTable(id="port-table")
        yield Static("─── Summary ───", classes="section-header")
        yield PortSummary(id="port-summary")
