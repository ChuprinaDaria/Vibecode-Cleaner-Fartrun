"""Docker Monitor TUI widget."""

from __future__ import annotations

from textual.widgets import DataTable, Static
from textual.containers import Vertical


def fmt_bytes(n: int) -> str:
    if n >= 1_073_741_824:
        return f"{n / 1_073_741_824:.1f}GB"
    if n >= 1_048_576:
        return f"{n / 1_048_576:.0f}MB"
    if n >= 1024:
        return f"{n / 1024:.0f}KB"
    return f"{n}B"


class DockerTable(DataTable):
    def on_mount(self) -> None:
        self.add_columns("", "NAME", "STATUS", "CPU%", "RAM", "PORTS", "HEALTH")
        self.cursor_type = "row"

    def update_data(self, containers: list[dict]) -> None:
        self.clear()
        for c in containers:
            status = c.get("status", "unknown")
            if status == "running":
                icon = "[green]●[/]"
            elif status == "exited":
                icon = "[dim]○[/]"
            else:
                icon = "[yellow]◉[/]"

            cpu = c.get("cpu_percent", 0)
            cpu_str = f"{cpu:.1f}%" if status == "running" else "—"
            if cpu > 80:
                cpu_str = f"[red]{cpu_str}[/]"
            elif cpu > 50:
                cpu_str = f"[yellow]{cpu_str}[/]"

            mem = fmt_bytes(c.get("mem_usage", 0)) if status == "running" else "—"

            ports_list = c.get("ports", [])
            ports_str = ", ".join(f"{p['host_port']}→{p['container_port']}" for p in ports_list[:3])
            if len(ports_list) > 3:
                ports_str += f" +{len(ports_list) - 3}"

            health = c.get("health") or "—"

            self.add_row(icon, c.get("name", "?"), status, cpu_str, mem, ports_str, health)


class EventsLog(Static):
    def update_events(self, events: list[dict]) -> None:
        lines = []
        for e in events[-10:]:
            ts = e.get("timestamp", "")[:5] if e.get("timestamp") else ""
            lines.append(f"{ts}  {e.get('message', '')}")
        self.update("\n".join(lines) if lines else "No recent events")


class DockerMonitorWidget(Vertical):
    def compose(self):
        yield DockerTable(id="docker-table")
        yield Static("─── Events ───", classes="section-header")
        yield EventsLog(id="docker-events")
