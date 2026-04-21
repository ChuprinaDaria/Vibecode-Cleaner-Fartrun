"""HealthPage — Dev Health UI with human-language scan results."""
from __future__ import annotations

import logging
import shlex
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from core.health.models import HealthFinding, HealthReport
from core.health.test_detector import detect_framework
from core.health.test_runner import TestRunner
from core.health.test_parsers import for_framework
from core.history import HistoryDB
from gui.copyable_widgets import make_copy_all_button
from gui.pages.health.test_runner_thread import TestRunnerThread
from gui.pages.health.threads import HaikuHealthThread, HealthScanThread
from gui.win95 import (
    BUTTON_STYLE, FONT_MONO, FONT_UI, GROUP_STYLE, NOTIFICATION_BG,
    NOTIFICATION_BORDER, PAGE_TITLE_STYLE, PRIMARY_BUTTON_STYLE, SHADOW,
    TITLE_DARK, severity_color,
)
from i18n import get_language, get_string as _t

log = logging.getLogger("fartrun.health_page")


class HealthPage(QWidget):
    """Dev Health — scan project and show health check results."""

    def __init__(self):
        super().__init__()
        self._project_dir: str | None = None
        self._scan_thread: HealthScanThread | None = None
        self._haiku_thread: HaikuHealthThread | None = None
        self._config: dict = {}
        self._all_texts: list[str] = []
        # Test runner state
        self._test_thread: TestRunnerThread | None = None
        self._needs_rerun: bool = False
        self._test_status_label = None
        self._test_run_button = None
        self._test_elapsed_timer: QTimer | None = None
        self._test_run_started_monotonic: float | None = None
        self._build_ui()

    _haiku_error_callback = None

    def set_haiku_error_callback(self, callback) -> None:
        """Set callback invoked when HaikuClient hits an API error."""
        self._haiku_error_callback = callback

    def set_config(self, config: dict) -> None:
        self._config = config

    def hide_dir_picker(self) -> None:
        """Hide per-page dir picker when shared project selector is active."""
        if hasattr(self, '_btn_select'):
            self._btn_select.hide()
        if hasattr(self, '_dir_label'):
            self._dir_label.hide()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header = QHBoxLayout()
        title = QLabel(_t("health_header"))
        title.setFont(QFont("Tahoma", 14, QFont.Bold))
        title.setStyleSheet(PAGE_TITLE_STYLE)
        header.addWidget(title)
        header.addStretch()

        self._dir_label = QLabel(_t("health_no_dir"))
        self._dir_label.setStyleSheet(f"color: {SHADOW};")
        header.addWidget(self._dir_label)

        self._btn_select = QPushButton(_t("health_btn_select"))
        self._btn_select.setStyleSheet(BUTTON_STYLE)
        self._btn_select.clicked.connect(self._on_select_dir)
        header.addWidget(self._btn_select)

        self._btn_scan = QPushButton(_t("health_btn_scan"))
        self._btn_scan.clicked.connect(self._on_scan)
        self._btn_scan.setEnabled(False)
        self._btn_scan.setStyleSheet(PRIMARY_BUTTON_STYLE)
        header.addWidget(self._btn_scan)
        header.addWidget(make_copy_all_button(lambda: "\n".join(self._all_texts)))

        layout.addLayout(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 2px inset {SHADOW}; background: white; }}"
        )

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._content_widget)

        layout.addWidget(scroll)

        layout.addWidget(self._build_tests_section())

        self._show_placeholder(_t("health_select_dir"))

    def _show_placeholder(self, text: str) -> None:
        self._clear_content()
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #808080; font-size: 14px; padding: 40px;")
        self._content_layout.addWidget(lbl)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _build_tests_section(self) -> QGroupBox:
        from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout
        box = QGroupBox(_t("tests_section_title"))
        box.setStyleSheet(GROUP_STYLE)
        v = QVBoxLayout(box)

        row = QHBoxLayout()
        self._test_status_label = QLabel(_t("tests_status_idle"))
        self._test_status_label.setStyleSheet(f"font-family: {FONT_UI};")
        row.addWidget(self._test_status_label, stretch=1)

        self._test_run_button = QPushButton(_t("tests_btn_run"))
        self._test_run_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._test_run_button.clicked.connect(self._on_run_tests)
        row.addWidget(self._test_run_button)

        v.addLayout(row)
        return box

    def _on_run_tests(self) -> None:
        if self._test_thread is not None and self._test_thread.isRunning():
            self._needs_rerun = True
            self._update_test_status_running()
            return
        if not self._project_dir:
            return
        framework, default_cmd = detect_framework(Path(self._project_dir))
        override = (self._config.get("tests", {}) or {}).get("command", "") or ""
        cmd = shlex.split(override) if override.strip() else default_cmd
        if not cmd:
            self._test_status_label.setText(_t("tests_no_framework"))
            return

        timeout = int((self._config.get("tests", {}) or {}).get("timeout_s", 600))
        runner = TestRunner(parser=for_framework(framework),
                            timeout_s=timeout, framework=framework)
        thread = TestRunnerThread(runner, Path(self._project_dir), cmd)
        thread.finished_run.connect(self._on_test_finished)
        self._test_thread = thread
        self._test_run_button.setEnabled(False)
        self._needs_rerun = False
        import time as _time
        self._test_run_started_monotonic = _time.monotonic()
        self._update_test_status_running()
        if self._test_elapsed_timer is None:
            self._test_elapsed_timer = QTimer(self)
            self._test_elapsed_timer.timeout.connect(self._update_test_status_running)
        self._test_elapsed_timer.start(1000)
        thread.start()

    def _update_test_status_running(self) -> None:
        if self._test_status_label is None or self._test_run_started_monotonic is None:
            return
        import time as _time
        elapsed = int(_time.monotonic() - self._test_run_started_monotonic)
        key = "tests_status_running_queued" if self._needs_rerun else "tests_status_running"
        self._test_status_label.setText(_t(key).format(seconds=elapsed))

    def _on_test_finished(self, run) -> None:
        if self._test_elapsed_timer is not None:
            self._test_elapsed_timer.stop()
        try:
            HistoryDB().save_test_run(self._test_run_to_dict(run))
        except Exception as e:
            log.warning("save_test_run failed: %s", e)

        self._test_thread = None
        self._test_run_started_monotonic = None
        self._test_run_button.setEnabled(True)
        self._render_test_status_for(run)

        if self._needs_rerun:
            self._needs_rerun = False
            self._on_run_tests()

    @staticmethod
    def _test_run_to_dict(run) -> dict:
        return {
            "project_dir": run.project_dir, "framework": run.framework,
            "command": run.command, "started_at": run.started_at,
            "finished_at": run.finished_at, "duration_s": run.duration_s,
            "exit_code": run.exit_code, "timed_out": run.timed_out,
            "passed": run.passed, "failed": run.failed,
            "errors": run.errors, "skipped": run.skipped,
            "output_tail": run.output_tail,
        }

    def _render_test_status_for(self, run) -> None:
        if self._test_status_label is None:
            return
        if run.timed_out:
            self._test_status_label.setText(
                _t("tests_status_timed_out").format(duration=_format_duration(run.duration_s))
            )
            return
        if run.exit_code == 0 and not run.timed_out:
            self._test_status_label.setText(
                _t("tests_status_passed").format(duration=_format_duration(run.duration_s))
            )
            return
        if run.exit_code == -1:
            self._test_status_label.setText(
                _t("tests_status_error").format(message=run.output_tail.splitlines()[0] if run.output_tail else "error")
            )
            return
        if run.passed is None:
            self._test_status_label.setText(_t("tests_status_failed_unknown"))
            self._test_status_label.setToolTip(run.output_tail or "")
            return
        total = (run.passed or 0) + (run.failed or 0) + (run.errors or 0)
        # Extract failed test names from output for human-readable detail
        failed_names = _extract_failed_names(run.output_tail or "")
        detail = ""
        if failed_names:
            detail = "\n" + "\n".join(f"  · {n}" for n in failed_names[:5])
        status_text = _t("tests_status_failed_counts").format(
            failed=run.failed or 0, total=total,
        )
        if detail:
            status_text += detail
        self._test_status_label.setText(status_text)
        self._test_status_label.setToolTip(run.output_tail or "")

    def _on_select_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self, _t("health_btn_select"), str(Path.home()),
        )
        if dir_path:
            self._project_dir = dir_path
            display = dir_path if len(dir_path) <= 50 else "..." + dir_path[-47:]
            self._dir_label.setText(display)
            self._dir_label.setStyleSheet("color: #000000;")
            self._btn_scan.setEnabled(True)
            self._show_placeholder(_t("health_no_results"))
            self._start_watch_observer()

    def _on_scan(self) -> None:
        if not self._project_dir:
            return
        self._btn_scan.setEnabled(False)
        self._btn_scan.setText(_t("health_scanning"))
        self._show_placeholder(_t("health_scanning"))

        self._scan_thread = HealthScanThread(self._project_dir, self)
        self._scan_thread.scan_done.connect(self._on_scan_done)
        self._scan_thread.start()

    def _on_scan_done(self, report: HealthReport) -> None:
        self._btn_scan.setEnabled(True)
        self._btn_scan.setText(_t("health_btn_scan"))
        self._all_texts.clear()
        self._last_report = report
        self._render_report(report)
        # Save report to .fartrun/reports/
        try:
            from core.health.report_md import save_report_md
            path = save_report_md(report)
            log.info("Health report saved: %s", path)
        except Exception as e:
            log.warning("Failed to save health report: %s", e)
        # Trigger Haiku
        if report.findings:
            self._haiku_thread = HaikuHealthThread(report.findings, self._config, on_api_error=self._haiku_error_callback)
            self._haiku_thread.done.connect(self._on_haiku_done)
            self._haiku_thread.start()

    def _on_haiku_done(self, explanations: dict, summary: str) -> None:
        if not summary and not explanations:
            return

        box = QFrame()
        box.setStyleSheet(
            f"QFrame {{ border: 2px solid {NOTIFICATION_BORDER}; "
            f"background: {NOTIFICATION_BG}; padding: 6px; margin-bottom: 4px; }}"
        )
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(8, 6, 8, 6)
        box_layout.setSpacing(4)

        title = QLabel(f"-- {_t('health_ai_summary')} --")
        title.setStyleSheet(
            f"font-weight: bold; color: #806600; font-size: 12px; "
            f"font-family: {FONT_UI};"
        )
        box_layout.addWidget(title)

        if summary:
            lbl = QLabel(summary)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: #333; font-size: 12px; padding: 4px; font-family: {FONT_UI};"
            )
            box_layout.addWidget(lbl)
            self._all_texts.insert(0, f"[AI] {summary}")

        if explanations:
            for expl in explanations.values():
                expl_lbl = QLabel(f"  {expl}")
                expl_lbl.setWordWrap(True)
                expl_lbl.setStyleSheet(
                    f"color: #555; font-size: 11px; padding: 1px 4px; "
                    f"font-family: {FONT_UI};"
                )
                box_layout.addWidget(expl_lbl)
                self._all_texts.append(f"  [AI] {expl}")

        self._content_layout.insertWidget(0, box)

    def _render_report(self, report: HealthReport) -> None:
        self._clear_content()

        if not report.findings:
            self._show_placeholder(_t("health_empty_project"))
            return

        # Group findings by check_id
        sections: dict[str, tuple[str, list[HealthFinding]]] = {
            "map.file_tree": (_t("health_section_tree"), []),
            "map.entry_points": (_t("health_section_entry"), []),
            "map.modules": (_t("health_section_modules"), []),
            "map.monsters": (_t("health_section_monsters"), []),
            "map.configs": (_t("health_section_configs"), []),
            "dead.unused_imports": (_t("health_section_unused_imports"), []),
            "dead.unused_definitions": (_t("health_section_unused_defs"), []),
            "dead.orphan_files": (_t("health_section_orphans"), []),
            "dead.commented_code": (_t("health_section_commented"), []),
            "dead.duplicates": (_t("health_section_duplicates"), []),
            "debt.no_types": (_t("health_section_missing_types"), []),
            "debt.error_handling": (_t("health_section_error_gaps"), []),
            "debt.hardcoded": (_t("health_section_hardcoded"), []),
            "debt.todos": (_t("health_section_todos"), []),
            "debt.outdated_deps": (_t("health_section_outdated_deps"), []),
            "debt.no_reuse": (_t("health_section_reusable"), []),
            "brake.unfinished": (_t("health_section_unfinished"), []),
            "brake.tests": (_t("health_section_tests"), []),
            "brake.scope_creep": (_t("health_section_scope"), []),
            "brake.overengineering": (_t("health_section_overeng"), []),
            "brake.opensource_check": (_t("health_section_opensource"), []),
            "git.status": (_t("health_section_git_status"), []),
            "git.commits": (_t("health_section_git_commits"), []),
            "git.branches": (_t("health_section_git_branches"), []),
            "git.gitignore": (_t("health_section_git_ignore"), []),
            "git.cheatsheet": (_t("health_section_git_cheat"), []),
            "docs.readme": (_t("health_section_readme"), []),
            "docs.deps": (_t("health_section_deps"), []),
            "docs.devtools": (_t("health_section_devtools"), []),
            "docs.llm_context": (_t("health_section_llm_context"), []),
            "docs.ui_dictionary": (_t("health_section_ui_dict"), []),
            "docs.sdk_context": (_t("health_section_sdk_context"), []),
            "uiux.qss_slop": (_t("health_section_ai_slop"), []),
            "uiux.qss_quality": (_t("health_section_qss_quality"), []),
            "uiux.impeccable": (_t("health_section_ai_slop_web"), []),
            "uiux.stylelint": (_t("health_section_css_quality"), []),
            "uiux.lighthouse": (_t("health_section_lighthouse"), []),
            "uiux.pa11y": (_t("health_section_pa11y"), []),
            "system": ("System", []),
        }

        for finding in report.findings:
            key = finding.check_id
            if key in sections:
                sections[key][1].append(finding)

        # File tree summary
        if report.file_tree:
            tree = report.file_tree
            group = self._make_group(
                f"{_t('health_section_tree')} \u2014 "
                f"{tree['total_files']} {_t('health_files_label')} | "
                f"{tree['total_dirs']} {_t('health_dirs_label')} | "
                f"{self._format_size(tree['total_size_bytes'])} | "
                f"{_t('health_depth_label')} {tree['max_depth']}"
            )
            gl = group.layout()
            ext_sorted = sorted(
                tree["files_by_ext"].items(), key=lambda x: x[1], reverse=True
            )
            ext_str = "  ".join(f".{ext}: {count}" for ext, count in ext_sorted[:8])
            ext_lbl = QLabel(ext_str)
            ext_lbl.setStyleSheet("font-family: monospace; color: #333; padding: 4px;")
            gl.addWidget(ext_lbl)
            tree_findings = sections.get("map.file_tree", ("", []))[1]
            if tree_findings:
                tip = QLabel(f"  {tree_findings[0].message}")
                tip.setStyleSheet("color: #666; font-size: 11px;")
                tip.setWordWrap(True)
                gl.addWidget(tip)
            self._content_layout.addWidget(group)

        # Entry points
        if report.entry_points:
            ep_findings = sections.get("map.entry_points", ("", []))[1]
            group = self._make_group(
                f"{_t('health_section_entry')} ({len(report.entry_points)})"
            )
            gl = group.layout()
            for ep in report.entry_points:
                row = QLabel(f"  \u25cf {ep['path']} \u2014 {ep['description']}")
                row.setStyleSheet("color: #333; padding: 2px;")
                gl.addWidget(row)
            if ep_findings:
                tip = QLabel(f"  {ep_findings[0].message}")
                tip.setStyleSheet("color: #666; font-size: 11px;")
                tip.setWordWrap(True)
                gl.addWidget(tip)
            self._content_layout.addWidget(group)

        # Module hubs / circular / orphans
        module_findings = sections.get("map.modules", ("", []))[1]
        if module_findings:
            group = self._make_group(_t("health_section_modules"))
            gl = group.layout()
            for f in module_findings:
                row = self._make_finding_row(f)
                gl.addWidget(row)
            self._content_layout.addWidget(group)

        # Monsters
        if report.monsters:
            group = self._make_group(_t("health_section_monsters"))
            gl = group.layout()
            for m in report.monsters:
                sev_icon = self._severity_icon(m["severity"])
                row = QLabel(
                    f"  {sev_icon} {m['path']} \u2014 {m['lines']} lines, "
                    f"{m['functions']} functions, {m['classes']} classes"
                )
                color = self._severity_color(m["severity"])
                row.setStyleSheet(f"color: {color}; font-weight: bold; padding: 2px;")
                gl.addWidget(row)
            monster_findings = sections.get("map.monsters", ("", []))[1]
            for f in monster_findings[:3]:
                tip = QLabel(f"  {f.message}")
                tip.setStyleSheet("color: #666; font-size: 11px;")
                tip.setWordWrap(True)
                gl.addWidget(tip)
            self._content_layout.addWidget(group)

        # Configs
        if report.configs:
            group = self._make_group(
                f"{_t('health_section_configs')} ({len(report.configs)})"
            )
            gl = group.layout()
            for c in report.configs:
                icon = "\u26a0\ufe0f" if c["severity"] == "warning" else "\u2139\ufe0f"
                row = QLabel(f"  {icon} {c['path']} \u2014 {c['description']}")
                row.setStyleSheet("color: #333; padding: 2px;")
                gl.addWidget(row)
            config_findings = sections.get("map.configs", ("", []))[1]
            for f in config_findings:
                tip = QLabel(f"  {f.message}")
                tip.setStyleSheet("color: #666; font-size: 11px;")
                tip.setWordWrap(True)
                gl.addWidget(tip)
            self._content_layout.addWidget(group)

        # Dead Code sections
        for dead_key in [
            "dead.unused_imports", "dead.unused_definitions", "dead.orphan_files", "dead.commented_code", "dead.duplicates",
            "debt.no_types", "debt.error_handling", "debt.hardcoded", "debt.todos", "debt.outdated_deps", "debt.no_reuse",
            "brake.unfinished", "brake.tests", "brake.scope_creep", "brake.overengineering",
            "git.status", "git.commits", "git.branches", "git.gitignore", "git.cheatsheet",
            "docs.readme", "docs.deps", "docs.devtools", "docs.llm_context",
            "docs.ui_dictionary", "docs.sdk_context",
            "uiux.qss_slop", "uiux.qss_quality",
            "uiux.impeccable", "uiux.stylelint", "uiux.lighthouse", "uiux.pa11y",
        ]:
            dead_findings = sections.get(dead_key, ("", []))[1]
            if dead_findings:
                section_title = sections[dead_key][0]
                group = self._make_group(f"{section_title} ({len(dead_findings)})")
                gl = group.layout()
                for f in dead_findings[:15]:
                    row = self._make_finding_row(f)
                    gl.addWidget(row)
                    # Special: UI Dictionary button
                    if f.check_id == "docs.ui_dictionary":
                        btn = QPushButton(_t("health_btn_ui_dict"))
                        btn.setStyleSheet(
                            "QPushButton { background: #000080; color: white; "
                            "padding: 4px 12px; border: 2px outset #4040c0; "
                            "font-weight: bold; max-width: 200px; }"
                        )
                        btn.clicked.connect(self._show_ui_dictionary)
                        gl.addWidget(btn)
                    # Special: SDK Context button
                    if f.check_id == "docs.sdk_context":
                        btn = QPushButton(_t("health_btn_sdk_fetch"))
                        btn.setStyleSheet(
                            "QPushButton { padding: 4px 12px; max-width: 200px; }"
                        )
                        btn.clicked.connect(self._show_sdk_context)
                        gl.addWidget(btn)
                if len(dead_findings) > 15:
                    more = QLabel(f"  ... and {len(dead_findings) - 15} more")
                    more.setStyleSheet("color: #808080; font-style: italic;")
                    gl.addWidget(more)
                self._content_layout.addWidget(group)

        # System warnings
        sys_findings = sections.get("system", ("", []))[1]
        for f in sys_findings:
            row = self._make_finding_row(f)
            self._content_layout.addWidget(row)

        # Summary bar
        self._add_summary_bar(report)

        self._content_layout.addStretch()

    def _add_summary_bar(self, report: HealthReport) -> None:
        counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in report.findings:
            if f.severity in counts:
                counts[f.severity] += 1

        parts = []
        icons = {
            "critical": "\U0001f480",
            "high": "\U0001f534",
            "medium": "\U0001f7e1",
            "low": "\U0001f535",
            "info": "\u2139\ufe0f",
        }
        for sev in ["critical", "high", "medium", "low", "info"]:
            if counts[sev] > 0:
                parts.append(f"{icons[sev]} {counts[sev]} {_t(f'health_severity_{sev}')}")

        if parts:
            summary = QLabel("  " + " | ".join(parts))
            summary.setStyleSheet(
                f"background: #e0e0e0; border: 2px groove {SHADOW}; "
                f"padding: 6px; font-weight: bold; margin-top: 8px; "
                f"font-family: {FONT_UI};"
            )
            self._content_layout.addWidget(summary)

    def _make_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(GROUP_STYLE)
        layout = QVBoxLayout(group)
        layout.setSpacing(2)
        return group

    def _make_finding_row(self, finding: HealthFinding) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { border-bottom: 1px solid #e0e0e0; padding: 4px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        color = self._severity_color(finding.severity)
        icon = self._severity_icon(finding.severity)

        title_lbl = QLabel(f"{icon} {finding.title}")
        title_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(title_lbl)

        msg_lbl = QLabel(f"  {finding.message}")
        msg_lbl.setStyleSheet("color: #666; font-size: 11px;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)
        self._all_texts.append(f"[{finding.severity}] {finding.title}: {finding.message}")

        return frame

    @staticmethod
    def _severity_color(severity: str) -> str:
        return {
            "critical": "#8b0000",
            "high": "#cc0000",
            "medium": "#cc6600",
            "low": "#000080",
            "info": "#333333",
            "warning": "#cc6600",
        }.get(severity, "#808080")

    @staticmethod
    def _severity_icon(severity: str) -> str:
        return {
            "critical": "\U0001f480",
            "high": "\U0001f534",
            "medium": "\U0001f7e1",
            "low": "\U0001f535",
            "info": "\u2139\ufe0f",
            "warning": "\u26a0\ufe0f",
        }.get(severity, "")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _show_ui_dictionary(self) -> None:
        """Open UI Dictionary popup."""
        from gui.ui_dictionary_popup import UIDictionaryPopup
        lang = get_language()
        popup = UIDictionaryPopup(lang=lang, parent=self)
        popup.exec_()

    def _show_sdk_context(self) -> None:
        """Open SDK Context fetch dialog."""
        from gui.sdk_context_popup import SDKContextPopup
        popup = SDKContextPopup(
            project_dir=self._project_dir,
            config=self._config,
            parent=self,
        )
        popup.exec_()

    def _on_watch_event(self) -> None:
        if not (self._config.get("tests", {}) or {}).get("watch"):
            return
        debounce = int((self._config.get("tests", {}) or {}).get("debounce_ms", 2000))
        if not hasattr(self, "_watch_debounce_timer") or self._watch_debounce_timer is None:
            from PyQt5.QtCore import QTimer
            self._watch_debounce_timer = QTimer(self)
            self._watch_debounce_timer.setSingleShot(True)
            self._watch_debounce_timer.timeout.connect(self._on_run_tests)
        self._watch_debounce_timer.start(debounce)

    def _start_watch_observer(self) -> None:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            log.info("watchdog not installed; watch mode disabled")
            return
        if not self._project_dir:
            return
        cfg = self._config.get("tests", {}) or {}
        if not cfg.get("watch"):
            return
        watch_paths = cfg.get("watch_paths") or ["."]
        excludes = set(cfg.get("watch_exclude") or [])

        page = self
        class _Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.is_directory:
                    return
                p = event.src_path
                if any(part in excludes for part in Path(p).parts):
                    return
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, page._on_watch_event)

        self._watch_observer = Observer()
        for wp in watch_paths:
            self._watch_observer.schedule(_Handler(), str(Path(self._project_dir) / wp), recursive=True)
        self._watch_observer.start()

    def _stop_watch_observer(self) -> None:
        obs = getattr(self, "_watch_observer", None)
        if obs is not None:
            obs.stop()
            obs.join(timeout=2)
            self._watch_observer = None

    def closeEvent(self, event):
        self._stop_watch_observer()
        super().closeEvent(event)

    def _on_save_point_created(self, project_dir: str) -> None:
        if not (self._config.get("tests", {}) or {}).get("trigger_on_save_point"):
            return
        if project_dir != self._project_dir:
            return
        self._on_run_tests()


def _extract_failed_names(output: str) -> list[str]:
    """Pull failed test names from pytest/cargo/jest output."""
    import re
    names: list[str] = []
    for line in output.splitlines():
        # pytest: "FAILED tests/test_foo.py::test_bar - ..."
        m = re.match(r"^FAILED\s+(.+?)(?:\s+-\s+|$)", line)
        if m:
            names.append(m.group(1).strip())
            continue
        # pytest short summary: "tests/test_foo.py::test_bar"
        if "::" in line and ("FAILED" in line or "ERROR" in line):
            part = line.split()[-1] if line.split() else line
            if "::" in part and part not in names:
                names.append(part)
    return names


def _format_duration(seconds: float | None) -> str:
    if not seconds:
        return "0s"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60}s"
