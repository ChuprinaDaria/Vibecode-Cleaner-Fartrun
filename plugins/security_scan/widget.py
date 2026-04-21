"""Security Scan TUI widget."""

from __future__ import annotations

from textual.widgets import DataTable, Static
from textual.containers import Vertical


SEVERITY_ICONS = {
    "critical": "[red bold]CRIT[/]",
    "high": "[#ff8c00]HIGH[/]",
    "medium": "[yellow]MED[/]",
    "low": "[dim]LOW[/]",
}


class FindingsTable(DataTable):
    def on_mount(self) -> None:
        self.add_columns("SEV", "TYPE", "DESCRIPTION", "SOURCE")
        self.cursor_type = "row"

    def update_data(self, findings: list[dict]) -> None:
        self.clear()
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda f: order.get(f.get("severity", "low"), 4))

        for f in findings:
            sev = SEVERITY_ICONS.get(f["severity"], f["severity"])
            desc = f["description"][:80]
            source = f.get("source", "")[:30]
            self.add_row(sev, f.get("type", ""), desc, source)


class SecuritySummary(Static):
    def update_counts(self, findings: list[dict]) -> None:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            sev = f.get("severity", "low")
            counts[sev] = counts.get(sev, 0) + 1
        self.update(
            f"[red bold]CRITICAL ({counts['critical']})[/]  "
            f"[#ff8c00]HIGH ({counts['high']})[/]  "
            f"[yellow]MEDIUM ({counts['medium']})[/]  "
            f"[dim]LOW ({counts['low']})[/]"
        )


class SecurityWidget(Vertical):
    def compose(self):
        yield SecuritySummary(id="security-summary")
        yield FindingsTable(id="security-table")
