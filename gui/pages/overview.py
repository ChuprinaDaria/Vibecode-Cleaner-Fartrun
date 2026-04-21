"""Overview page — status, budget, tokens, usage breakdown, infra, security.

Absorbs the former dedicated Usage page. Sections are authentic Win95
GroupBox containers with bevels; the only gradient lives on the cost
metric (an exception to stay visually grounded). The whole thing sits
inside a QScrollArea so narrow windows never clip content.
"""

from datetime import datetime

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from core.changelog_watcher import CHANGELOG_URL
from core.token_parser import TokenParser
from gui.copyable_table import CopyableTableWidget
from gui.fmt_utils import fmt_tokens as _fmt
from gui.win95 import (
    COMPACT_STYLE as _COMPACT_STYLE,
    GROUP_STYLE as _GROUP_STYLE,
    NUM_STYLE as _NUM_STYLE,
    TITLE_DARK,
    traffic_light,
)
from i18n import get_string as _t

_STATUS_MAP = {
    "none": "OK",
    "minor": "Degraded",
    "major": "Down",
    "critical": "Down",
    "unknown": "Unknown",
}


class OverviewPage(QWidget):
    nag_requested = pyqtSignal()
    hoff_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._subscription = None
        self._parser = TokenParser()

        # Wrap everything in a scroll area — prevents clipping on small
        # windows and lets us stack many sections vertically.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)

        self._build_claude_status(layout)
        self._build_budget(layout)
        self._build_tokens(layout)
        self._build_usage_breakdown(layout)
        self._build_models_projects(layout)
        self._build_weekly_trends(layout)
        self._build_infra(layout)
        self._build_security(layout)
        self._build_nag_and_hoff(layout)

        layout.addStretch()

    # ---------------------------------------------------------- sections

    def _build_claude_status(self, parent: QVBoxLayout) -> None:
        self.claude_group = QGroupBox(_t("status_claude_status"))
        self.claude_group.setStyleSheet(_GROUP_STYLE)
        cl = QVBoxLayout()
        cl.setSpacing(4)

        status_row = QHBoxLayout()
        self.lbl_claude_version = QLabel("Version: --")
        self.lbl_claude_version.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self.lbl_claude_version)

        self.lbl_api_status = QLabel(_t("status_unknown"))
        self.lbl_api_status.setWordWrap(True)
        self.lbl_api_status.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        status_row.addWidget(self.lbl_api_status, 1)

        self.lbl_last_check = QLabel("")
        self.lbl_last_check.setStyleSheet("color: #808080; font-size: 11px;")
        status_row.addWidget(self.lbl_last_check)

        self.btn_check_now = QPushButton(_t("status_check_now"))
        self.btn_check_now.setFixedWidth(100)
        status_row.addWidget(self.btn_check_now)
        cl.addLayout(status_row)

        self.lbl_dont_panic = QLabel(_t("status_dont_panic"))
        self.lbl_dont_panic.setWordWrap(True)
        self.lbl_dont_panic.setStyleSheet(
            "color: #800000; padding: 4px; background: #ffffcc; "
            "border: 1px solid #808080;"
        )
        self.lbl_dont_panic.setVisible(False)
        cl.addWidget(self.lbl_dont_panic)

        self.lbl_history_title = QLabel(_t("status_last_24h"))
        self.lbl_history_title.setStyleSheet("font-weight: bold; margin-top: 4px;")
        cl.addWidget(self.lbl_history_title)

        self.lbl_status_history = QLabel(_t("status_all_day_ok"))
        self.lbl_status_history.setStyleSheet(_COMPACT_STYLE)
        self.lbl_status_history.setWordWrap(True)
        cl.addWidget(self.lbl_status_history)

        self.lbl_version_title = QLabel(_t("status_version_history"))
        self.lbl_version_title.setStyleSheet("font-weight: bold; margin-top: 4px;")
        cl.addWidget(self.lbl_version_title)

        self.lbl_version_history = QLabel("--")
        self.lbl_version_history.setStyleSheet(_COMPACT_STYLE)
        self.lbl_version_history.setWordWrap(True)
        cl.addWidget(self.lbl_version_history)

        self.btn_changelog = QPushButton(_t("status_show_changelog"))
        self.btn_changelog.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CHANGELOG_URL))
        )
        cl.addWidget(self.btn_changelog)

        self.claude_group.setLayout(cl)
        parent.addWidget(self.claude_group)

    def _build_budget(self, parent: QVBoxLayout) -> None:
        budget_group = QGroupBox(_t("session_usage"))
        budget_group.setStyleSheet(_GROUP_STYLE)
        bl = QVBoxLayout()
        bl.setSpacing(4)

        # Plan label — absorbed from Usage page. Navy pill in Win95 style.
        self.plan_label = QLabel("Plan: —")
        self.plan_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 4px 8px; "
            "background: #000080; color: white; "
            "border: 2px outset #4040c0;"
        )
        self.plan_label.setWordWrap(True)
        bl.addWidget(self.plan_label)

        self.budget_label = QLabel(_t("session_usage"))
        self.budget_label.setWordWrap(True)
        self.budget_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        bl.addWidget(self.budget_label)

        self.budget_bar = QProgressBar()
        self.budget_bar.setMaximum(100)
        bl.addWidget(self.budget_bar)

        self.cost_label = QLabel("--")
        self.cost_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #000080; "
            "border: 2px inset #808080; background: white; padding: 6px;"
        )
        self.cost_label.setAlignment(Qt.AlignCenter)
        self.cost_label.setWordWrap(False)
        bl.addWidget(self.cost_label)

        budget_group.setLayout(bl)
        parent.addWidget(budget_group)

    def _build_tokens(self, parent: QVBoxLayout) -> None:
        self.stats_group = QGroupBox(_t("tokens"))
        self.stats_group.setStyleSheet(_GROUP_STYLE)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        # Two columns of (label, value); each value gets _NUM_STYLE so
        # digits don't spill into adjacent cells.
        self.lbl_sessions = self._num_label("0")
        self.lbl_input = self._num_label("0")
        self.lbl_output = self._num_label("0")
        self.lbl_cache_read = self._num_label("0")
        self.lbl_cache_write = self._num_label("0")
        self.lbl_billable = self._num_label("0")
        self.lbl_cache_eff = self._num_label("0%")
        self.lbl_cache_saved = self._num_label("$0.00")

        pairs = [
            (_t("lbl_sessions"), self.lbl_sessions),
            (_t("lbl_input_tokens"), self.lbl_input),
            (_t("lbl_output_tokens"), self.lbl_output),
            (_t("lbl_cache_read"), self.lbl_cache_read),
            (_t("lbl_cache_write"), self.lbl_cache_write),
            (_t("lbl_billable"), self.lbl_billable),
            (_t("lbl_cache_eff"), self.lbl_cache_eff),
            (_t("lbl_cache_saved"), self.lbl_cache_saved),
        ]
        for i, (text, value_lbl) in enumerate(pairs):
            row, col = divmod(i, 2)
            name = QLabel(text)
            name.setStyleSheet("font-size: 11px;")
            grid.addWidget(name, row, col * 2)
            grid.addWidget(value_lbl, row, col * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.stats_group.setLayout(grid)
        parent.addWidget(self.stats_group)

    def _build_usage_breakdown(self, parent: QVBoxLayout) -> None:
        """Today + This Week + cache bar (absorbed from Usage)."""
        group = QGroupBox(_t("this_week"))
        group.setStyleSheet(_GROUP_STYLE)
        gl = QVBoxLayout()
        gl.setSpacing(6)

        # Today / Week summary — 2 compact rows
        self.today_summary = QLabel("—")
        self.today_summary.setStyleSheet(_COMPACT_STYLE)
        self.today_summary.setWordWrap(True)
        gl.addWidget(self.today_summary)

        self.week_summary = QLabel("—")
        self.week_summary.setStyleSheet(_COMPACT_STYLE)
        self.week_summary.setWordWrap(True)
        gl.addWidget(self.week_summary)

        # Cache progress bar with label above
        self.cache_label = QLabel(_t("cache_eff_pct").format("0"))
        self.cache_label.setStyleSheet("font-size: 11px; margin-top: 4px;")
        gl.addWidget(self.cache_label)

        self.cache_bar = QProgressBar()
        self.cache_bar.setMaximum(100)
        gl.addWidget(self.cache_bar)

        self.savings_label = QLabel(_t("cache_saved_usd").format("0.00"))
        self.savings_label.setStyleSheet("font-size: 11px;")
        gl.addWidget(self.savings_label)

        group.setLayout(gl)
        parent.addWidget(group)

    def _build_models_projects(self, parent: QVBoxLayout) -> None:
        """Two tables side by side when wide, stacked when narrow."""
        models_group = QGroupBox(_t("model"))
        models_group.setStyleSheet(_GROUP_STYLE)
        ml = QVBoxLayout()
        self.model_table = CopyableTableWidget()
        self.model_table.setColumnCount(3)
        self.model_table.setHorizontalHeaderLabels(
            [_t("model"), _t("tokens"), _t("cost")]
        )
        self.model_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.model_table.setEditTriggers(CopyableTableWidget.NoEditTriggers)
        self.model_table.setMaximumHeight(160)
        ml.addWidget(self.model_table)
        models_group.setLayout(ml)
        parent.addWidget(models_group)

        projects_group = QGroupBox(_t("project"))
        projects_group.setStyleSheet(_GROUP_STYLE)
        pl = QVBoxLayout()
        self.project_table = CopyableTableWidget()
        self.project_table.setColumnCount(3)
        self.project_table.setHorizontalHeaderLabels(
            [_t("project"), _t("billable"), _t("sessions")]
        )
        self.project_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.project_table.setEditTriggers(CopyableTableWidget.NoEditTriggers)
        self.project_table.setMaximumHeight(220)
        pl.addWidget(self.project_table)
        projects_group.setLayout(pl)
        parent.addWidget(projects_group)

    def _build_weekly_trends(self, parent: QVBoxLayout) -> None:
        self.trends_group = QGroupBox(_t("weekly_trends"))
        self.trends_group.setStyleSheet(_GROUP_STYLE)
        tl = QVBoxLayout()
        tl.setSpacing(2)
        self.trend_labels: list[QLabel] = []
        for _ in range(7):
            lbl = QLabel("")
            lbl.setStyleSheet(
                "padding: 2px 4px; font-size: 11px; "
                "font-family: 'Fixedsys Excelsior', 'Courier New', monospace;"
            )
            tl.addWidget(lbl)
            self.trend_labels.append(lbl)
        self.trend_summary = QLabel("")
        self.trend_summary.setStyleSheet(
            "padding: 4px; font-weight: bold; font-size: 11px;"
        )
        tl.addWidget(self.trend_summary)
        self.trends_group.setLayout(tl)
        parent.addWidget(self.trends_group)

    def _build_infra(self, parent: QVBoxLayout) -> None:
        self.infra_group = QGroupBox("Infrastructure")
        self.infra_group.setStyleSheet(_GROUP_STYLE)
        il = QVBoxLayout()
        il.setSpacing(4)

        self.docker_status = QLabel("Docker: --")
        self.docker_status.setStyleSheet(_COMPACT_STYLE)
        self.docker_status.setWordWrap(True)
        il.addWidget(self.docker_status)

        self.ports_status = QLabel("Ports: --")
        self.ports_status.setStyleSheet(_COMPACT_STYLE)
        self.ports_status.setWordWrap(True)
        il.addWidget(self.ports_status)

        self.infra_group.setLayout(il)
        parent.addWidget(self.infra_group)

    def _build_security(self, parent: QVBoxLayout) -> None:
        sec_layout = QHBoxLayout()
        self.security_score = QLabel("--")
        self.security_score.setStyleSheet(
            "font-size: 32px; font-weight: bold; color: #000080; "
            "border: 2px inset #808080; background: white; "
            "padding: 6px; min-width: 72px;"
        )
        self.security_score.setAlignment(Qt.AlignCenter)
        sec_layout.addWidget(self.security_score)

        self.security_breakdown = QLabel("Security Score")
        self.security_breakdown.setWordWrap(True)
        self.security_breakdown.setStyleSheet("padding: 4px; font-size: 11px;")
        sec_layout.addWidget(self.security_breakdown, stretch=1)
        parent.addLayout(sec_layout)

    def _build_nag_and_hoff(self, parent: QVBoxLayout) -> None:
        self.nag_label = QLabel("")
        self.nag_label.setWordWrap(True)
        self.nag_label.setStyleSheet(
            "font-style: italic; padding: 8px; background: #ffffcc; "
            "color: #000; border: 2px inset #808080;"
        )
        parent.addWidget(self.nag_label)

        self.hoff_label = QLabel()
        self.hoff_label.setAlignment(Qt.AlignCenter)
        self.hoff_label.setFixedHeight(120)
        parent.addWidget(self.hoff_label)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton(_t("refresh"))
        self.btn_nag = QPushButton(_t("nag_me"))
        self.btn_hoff = QPushButton(_t("btn_hasselhoff"))
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        self.btn_nag.clicked.connect(self.nag_requested.emit)
        self.btn_hoff.clicked.connect(self.hoff_requested.emit)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_nag)
        btn_layout.addWidget(self.btn_hoff)
        parent.addLayout(btn_layout)

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _num_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(_NUM_STYLE)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl.setMinimumWidth(100)
        return lbl

    # --------------------------------------------------------- public API

    def set_subscription(self, sub: dict) -> None:
        self._subscription = sub

    def update_data(
        self,
        stats,
        cost,
        cache_eff: float,
        savings: float,
        nag_msg: str,
        sub: dict | None = None,
        comparison: dict | None = None,
        projects: list | None = None,
    ) -> None:
        """Main refresh. ``sub``/``comparison``/``projects`` drive the
        absorbed Usage sections; omitted means we only update the core
        Overview metrics."""
        sub = sub or self._subscription or {}
        comparison = comparison or {}
        projects = projects or []
        is_api = sub.get("is_paid_tokens")
        sub_type = sub.get("type", "unknown")
        is_sub = sub_type in ("pro", "max", "team")

        # --- Plan header ---
        if is_sub:
            tier = sub.get("tier", "")
            self.plan_label.setText(
                f"Plan: {sub_type.upper()}   |   Rate tier: {tier}"
            )
        else:
            self.plan_label.setText("Plan: API billing")

        # --- Budget ---
        if is_api:
            self.budget_label.setText(
                _t("api_cost_today").format(f"{cost.total_cost:.2f}")
            )
            self.cost_label.setText(f"${cost.total_cost:.2f}")
            pct = min(cost.total_cost / 10.0 * 100, 100)
        else:
            plan_name = sub_type.capitalize() if sub_type != "unknown" else "Plan"
            self.budget_label.setText(
                _t("session_info").format(
                    plan_name, len(stats.sessions), _fmt(stats.total_billable)
                )
            )
            self.cost_label.setText(f"{_fmt(stats.total_billable)} tok")
            pct = min(stats.total_billable / 1_000_000 * 100, 100)

        self.budget_bar.setValue(int(pct))
        cc = traffic_light(pct)
        self.budget_bar.setStyleSheet(f"QProgressBar::chunk {{ background: {cc}; }}")
        self.cost_label.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {cc}; "
            "border: 2px inset #808080; background: white; padding: 6px;"
        )

        # --- Tokens grid ---
        self.lbl_sessions.setText(str(len(stats.sessions)))
        self.lbl_input.setText(_fmt(stats.total_input))
        self.lbl_output.setText(_fmt(stats.total_output))
        self.lbl_cache_read.setText(_fmt(stats.total_cache_read))
        self.lbl_cache_write.setText(_fmt(stats.total_cache_write))
        self.lbl_billable.setText(_fmt(stats.total_billable))
        self.lbl_cache_eff.setText(f"{cache_eff:.1f}%")
        self.lbl_cache_saved.setText(f"~${savings:.2f}")

        # --- Today/Week summary ---
        self.today_summary.setText(
            f"{_t('today')}:  {len(stats.sessions)} sess  |  "
            f"{_fmt(stats.total_billable)} tok  |  "
            f"{_fmt(stats.total_input)} in / {_fmt(stats.total_output)} out"
        )
        try:
            week_data = self._parser.parse_range(days=7)
            week_sess = sum(len(d.sessions) for d in week_data)
            week_bill = sum(d.total_billable for d in week_data)
            self.week_summary.setText(
                f"{_t('this_week')}:  {week_sess} sess  |  {_fmt(week_bill)} tok"
            )
        except Exception:
            self.week_summary.setText(f"{_t('this_week')}:  —")

        # --- Cache bar ---
        self.cache_label.setText(_t("cache_eff_pct").format(f"{cache_eff:.1f}"))
        self.cache_bar.setValue(int(cache_eff))
        if is_sub:
            self.savings_label.setText(
                f"~{_fmt(int(savings / 0.000025))} tokens saved"
            )
        else:
            self.savings_label.setText(_t("cache_saved_usd").format(f"{savings:.2f}"))

        # --- Models table ---
        real_models = {
            m: mu for m, mu in stats.model_totals.items()
            if "claude" in m.lower() or "gpt" in m.lower()
        }
        if not real_models:
            real_models = stats.model_totals
        self.model_table.setRowCount(len(real_models))
        for i, (model, mu) in enumerate(real_models.items()):
            name = model.replace("claude-", "").replace("-", " ").upper()
            self.model_table.setItem(i, 0, QTableWidgetItem(name))
            self.model_table.setItem(i, 1, QTableWidgetItem(_fmt(mu.billable_tokens)))
            self.model_table.setItem(
                i, 2, QTableWidgetItem(f"${comparison.get('actual', 0):.2f}")
            )

        # --- Projects table ---
        self.project_table.setRowCount(min(len(projects), 10))
        for i, p in enumerate(projects[:10]):
            self.project_table.setItem(i, 0, QTableWidgetItem(p.project))
            self.project_table.setItem(
                i, 1, QTableWidgetItem(_fmt(p.total_billable))
            )
            self.project_table.setItem(i, 2, QTableWidgetItem(str(p.sessions)))

        # --- Nag ---
        self.nag_label.setText(f'"{nag_msg}"')

    def update_trends(self, history: list[dict]) -> None:
        """Last-7-day text bar chart. Absorbed from Usage."""
        if not history:
            return

        max_tokens = max((h["tokens"] for h in history), default=1) or 1
        for i, h in enumerate(history[:7]):
            if i >= len(self.trend_labels):
                break
            bar_len = int(h["tokens"] / max_tokens * 20)
            bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
            self.trend_labels[i].setText(
                f"{h['date'][-5:]}  {bar}  {h['tokens']/1000:>4.0f}K  "
                f"${h['cost']:.2f}"
            )

        if len(history) >= 2:
            today = history[0]["tokens"]
            yesterday = history[1]["tokens"]
            if yesterday > 0:
                change = (today - yesterday) / yesterday * 100
                arrow = "\u2191" if change > 0 else "\u2193"
                avg_cache = sum(
                    h["cache_efficiency"] for h in history
                ) / len(history)
                self.trend_summary.setText(
                    f"{arrow} {abs(change):.0f}% vs yesterday  |  "
                    f"Avg cache: {avg_cache:.0f}%"
                )

    def update_docker_compact(self, infos: list[dict]) -> None:
        running = sum(1 for i in infos if i.get("status") == "running")
        stopped = len(infos) - running
        alerts = 0
        for i in infos:
            if i.get("status") == "exited" and i.get("exit_code", 0) != 0:
                alerts += 1
            if i.get("cpu_percent", 0) > 80:
                alerts += 1
        text = f"Docker: {running} running | {stopped} stopped"
        if alerts:
            text += f" | {alerts} alerts"
        color = "#006600" if alerts == 0 else "#cc0000"
        self.docker_status.setText(text)
        self.docker_status.setStyleSheet(f"{_COMPACT_STYLE} color: {color};")

    def update_ports_compact(self, ports: list[dict]) -> None:
        total = len(ports)
        conflicts = sum(1 for p in ports if p.get("conflict"))
        text = f"Ports: {total} listening | {conflicts} conflicts"
        color = "#006600" if conflicts == 0 else "#cc8800"
        self.ports_status.setText(text)
        self.ports_status.setStyleSheet(f"{_COMPACT_STYLE} color: {color};")

    def update_security_score(self, findings: list[dict]) -> None:
        if not findings:
            self.security_score.setText("100")
            self.security_score.setStyleSheet(
                "font-size: 32px; font-weight: bold; color: #006600; "
                "border: 2px inset #808080; background: white; "
                "padding: 6px; min-width: 72px;"
            )
            self.security_breakdown.setText("No issues found")
            return

        deductions = {"critical": 20, "high": 10, "medium": 3, "low": 1}
        total_deduction = 0
        counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            sev = f.get("severity", "low")
            counts[sev] = counts.get(sev, 0) + 1
            total_deduction += deductions.get(sev, 1)

        score = max(0, 100 - total_deduction)
        color = "#006600" if score >= 80 else ("#cc8800" if score >= 50 else "#cc0000")

        self.security_score.setText(str(score))
        self.security_score.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {color}; "
            "border: 2px inset #808080; background: white; "
            "padding: 6px; min-width: 72px;"
        )

        parts = []
        for sev in ("critical", "high", "medium", "low"):
            if counts[sev] > 0:
                parts.append(f"{counts[sev]} {sev}")
        self.security_breakdown.setText(" | ".join(parts) if parts else "No issues")

    def set_docker_error(self, msg: str) -> None:
        self.docker_status.setText(f"Docker: {msg}")
        self.docker_status.setStyleSheet(f"{_COMPACT_STYLE} color: #999999;")

    def set_hoff_image(self, path: str) -> None:
        pixmap = QPixmap(path).scaledToHeight(100, Qt.SmoothTransformation)
        self.hoff_label.setPixmap(pixmap)

    def set_no_claude(self) -> None:
        self.budget_label.setText(_t("claude_not_found"))
        self.cost_label.setText("--")
        self.plan_label.setText(_t("no_analytics"))
        self.cache_label.setText(_t("no_analytics"))
        self.nag_label.setText(_t("set_claude_path"))

    def update_claude_status(self, result, history: list, version_history: list) -> None:
        if result.claude_version:
            self.lbl_claude_version.setText(
                _t("status_version").format(version=result.claude_version)
            )
        else:
            self.lbl_claude_version.setText(_t("status_claude_not_found"))

        indicator = result.api_indicator
        status_key = {
            "none": "status_ok", "minor": "status_degraded",
            "major": "status_down", "critical": "status_down",
        }.get(indicator, "status_unknown")
        self.lbl_api_status.setText(
            f"{_t(status_key)} -- {result.api_description}"
        )

        if indicator in ("major", "critical"):
            self.lbl_api_status.setStyleSheet("color: red; font-weight: bold;")
            self.lbl_dont_panic.setVisible(True)
            self.claude_group.setStyleSheet(
                _GROUP_STYLE
                + "QGroupBox { border: 2px groove #ff4444; }"
            )
        elif indicator == "minor":
            self.lbl_api_status.setStyleSheet("color: #808000; font-weight: bold;")
            self.lbl_dont_panic.setVisible(True)
            self.claude_group.setStyleSheet(
                _GROUP_STYLE
                + "QGroupBox { border: 2px groove #ffff00; }"
            )
        else:
            self.lbl_api_status.setStyleSheet("")
            self.lbl_dont_panic.setVisible(False)
            self.claude_group.setStyleSheet(_GROUP_STYLE)

        try:
            checked = datetime.fromisoformat(result.timestamp)
            delta = datetime.now() - checked
            minutes = int(delta.total_seconds() / 60)
            ago = "just now" if minutes < 1 else f"{minutes} min ago"
            self.lbl_last_check.setText(_t("status_checked_ago").format(ago=ago))
        except (ValueError, TypeError):
            pass

        if not history:
            self.lbl_status_history.setText(_t("status_all_day_ok"))
        else:
            lines = []
            for h in history[:10]:
                ts = h.timestamp[11:16] if len(h.timestamp) > 16 else h.timestamp
                label = _STATUS_MAP.get(h.api_indicator, "Unknown")
                desc = f" -- {h.api_description}" if h.api_description else ""
                lines.append(f"{ts}  {label}{desc}")
            self.lbl_status_history.setText("\n".join(lines))

        if version_history:
            lines = []
            for v in version_history[:5]:
                lines.append(f"{v[0]}  detected {v[1]}")
            self.lbl_version_history.setText("\n".join(lines))
