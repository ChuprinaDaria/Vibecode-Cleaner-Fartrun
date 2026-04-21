"""Main window — Win95 Explorer-style sidebar + content stack.

Smaller siblings (styles, threads, tray) live in their own modules
in this package so adding a new background task or styling tweak
doesn't grow this file further.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core.alerts import AlertManager
from core.autodiscovery import SystemState
from core.changelog_watcher import (
    _ensure_version_table, check_for_update, dismiss_version,
)
from core.history import HistoryDB
from core.platform import get_platform
from core.plugin import Alert
from core.plugin_loader import PluginRegistry
from core.status_checker import StatusChecker
from gui.app.styles import WIN95_STYLE
from gui.app.threads import DataCollectorThread, StatusCheckThread
from gui.pages.activity import ActivityPage
from gui.pages.discover import DiscoverTab
from gui.pages.hasselhoff_wizard import HasselhoffWizardPage
from gui.pages.health import HealthPage
from gui.pages.overview import OverviewPage
from gui.pages.prompt_helper import PromptHelperPage
from gui.pages.save_points_page import SavePointsPage
from gui.pages.security import SecurityPage, SecurityScanThread
from gui.pages.settings import SettingsPage
from gui.sidebar import Sidebar, SidebarItem
from gui.statusbar import ClaudeStatusBar
from gui.widgets.project_selector import ProjectSelector
from i18n import get_string as _t, set_language

log = logging.getLogger(__name__)


class MonitorApp(QMainWindow):
    """Main application window — Win95 Explorer style."""

    def __init__(self, config: dict, system_state: SystemState):
        super().__init__()
        self._config = config
        self._state = system_state
        self._alert_manager = AlertManager(config)

        self.setWindowTitle(_t("window_title"))
        self.setMinimumSize(950, 650)
        self.setStyleSheet(WIN95_STYLE)

        set_language(config.get("general", {}).get("language", "en"))

        self._create_menu_bar()

        # Central widget: sidebar + content stack
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar — no Docker/Ports, Hoff Wizard at end
        sidebar_items = [
            SidebarItem(_t("side_overview"), "overview"),
            SidebarItem(_t("side_activity"), "activity"),
            SidebarItem(_t("side_save_points"), "save_points"),
            SidebarItem(_t("side_prompt_helper"), "prompt_helper"),
            SidebarItem(_t("side_health"), "health"),
            SidebarItem(_t("side_security"), "security"),
            SidebarItem("", "", is_separator=True),
            SidebarItem(_t("side_discover"), "discover"),
            SidebarItem(_t("side_settings"), "settings"),
            SidebarItem("", "", is_separator=True),
            SidebarItem("Hoff Wizard", "hoff_wizard"),
            SidebarItem(_t("side_about"), "about"),
        ]
        self.sidebar = Sidebar(sidebar_items)
        self.sidebar.page_selected.connect(self._on_page_selected)
        main_layout.addWidget(self.sidebar)

        # Content stack
        self.stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}

        # Create pages (no Docker/Ports pages)
        self.page_overview = OverviewPage()
        self.page_security = SecurityPage()
        self.page_hoff_wizard = HasselhoffWizardPage()
        self.page_discover = DiscoverTab()
        self.page_activity = ActivityPage()
        self.page_activity.set_config(config)
        self.page_save_points = SavePointsPage()
        self.page_save_points.set_config(config)
        self.page_prompt_helper = PromptHelperPage()
        self.page_prompt_helper.set_config(config)
        self.page_health = HealthPage()
        self.page_health.set_config(config)
        self.page_settings = SettingsPage(config)

        from gui.pages.about import AboutPage
        self.page_about = AboutPage()

        for key, page in [
            ("overview", self.page_overview),
            ("activity", self.page_activity),
            ("save_points", self.page_save_points),
            ("prompt_helper", self.page_prompt_helper),
            ("health", self.page_health),
            ("security", self.page_security),
            ("hoff_wizard", self.page_hoff_wizard),
            ("discover", self.page_discover),
            ("settings", self.page_settings),
            ("about", self.page_about),
        ]:
            self.stack.addWidget(page)
            self._pages[key] = page

        # Right panel: project selector on top + content stack below
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Project selector — shared across Activity, Health, Snapshots
        _selector_db = HistoryDB()
        _claude_dir = str(system_state.claude_dir) if system_state.claude_dir else None
        self._project_selector = ProjectSelector(_selector_db, _claude_dir, parent=right_panel)
        self._project_selector.project_changed.connect(self._on_project_changed)
        right_layout.addWidget(self._project_selector)

        right_layout.addWidget(self.stack)
        main_layout.addWidget(right_panel)
        self.setCentralWidget(central)

        # Claude Status Bar (permanent, replaces default statusbar)
        self._claude_statusbar = ClaudeStatusBar(self)
        self.setStatusBar(self._claude_statusbar)
        self._claude_statusbar.clicked.connect(lambda: self._on_page_selected("overview"))

        # Wire save-point trigger → health test runner
        self.page_save_points.save_point_created.connect(
            self.page_health._on_save_point_created
        )

        # Connect signals
        self.page_overview.refresh_requested.connect(self._refresh_all)
        self.page_overview.nag_requested.connect(self._do_nag)
        self.page_overview.hoff_requested.connect(self._do_hoff)
        self.page_security.scan_requested.connect(self._run_security_scan)
        self.page_hoff_wizard.hoff_event.connect(self._trigger_hasselhoff)
        self.page_activity.refresh_requested.connect(self._refresh_all)
        self.page_settings.settings_changed.connect(self._on_settings_changed)

        # Plugin registry — loads enabled plugins (test_runner etc.)
        self._plugin_registry = PluginRegistry(
            config=self._config,
            db_path=get_platform().data_dir() / "history.db",
        )
        try:
            self._plugin_registry.start()
        except Exception as e:
            log.warning("Plugin registry start failed: %s", e)

        # Collector thread state (must init before any refresh calls)
        self._collector_thread = None
        self._collecting = False
        self._scan_thread = None
        self._last_security_score = 100
        self._history_db = None
        # Grace period — no popups for first 15 seconds after startup
        self._startup_grace = True
        self.page_security._suppress_popups = True
        QTimer.singleShot(15_000, self._end_startup_grace)

        # Hide per-page dir pickers — shared project selector takes over
        if hasattr(self.page_activity, 'hide_dir_picker'):
            self.page_activity.hide_dir_picker()
        self.page_health.hide_dir_picker()
        self.page_save_points.hide_dir_picker()

        # Propagate Haiku API error callback — triggers status re-check on failure
        self._on_haiku_api_error = lambda e: self._check_api_status()
        for page in (self.page_activity, self.page_health,
                     self.page_save_points, self.page_prompt_helper):
            if hasattr(page, "set_haiku_error_callback"):
                page.set_haiku_error_callback(self._on_haiku_api_error)

        # Push initial project to pages (restores last session's directory)
        initial_project = self._project_selector.current_project()
        if initial_project:
            self._on_project_changed(initial_project)

        # Apply autodiscovery state
        if not system_state.docker_available:
            self.page_overview.set_docker_error(
                system_state.docker_error or "Docker not available")
        if not system_state.claude_dir:
            self.page_overview.set_no_claude()

        # Unified refresh timer
        refresh_interval = config["general"]["refresh_interval"] * 1000
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_all)
        self._refresh_timer.start(refresh_interval)

        # Security scan timer
        scan_interval = config["plugins"]["security_scan"]["scan_interval"] * 1000
        self._security_timer = QTimer(self)
        self._security_timer.timeout.connect(self._run_security_scan)
        self._security_timer.start(scan_interval)

        # Snapshot auto timer
        snap_config = config.get("snapshots", {})
        if snap_config.get("enabled", True):
            snap_interval = snap_config.get("auto_interval_minutes", 30) * 60 * 1000
            self._snapshot_timer = QTimer(self)
            self._snapshot_timer.timeout.connect(self._auto_snapshot)
            self._snapshot_timer.start(snap_interval)

        # Status checker timer
        self._status_checker = None
        self._status_thread = None
        status_config = config.get("status", {})
        if status_config.get("enabled", True):
            interval_min = status_config.get("check_interval_minutes", 5)
            self._status_timer = QTimer(self)
            self._status_timer.timeout.connect(self._check_api_status)
            self._status_timer.start(interval_min * 60 * 1000)

        # Initial refresh
        self._refresh_all()
        self._run_security_scan()

    def _create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu(_t("menu_file"))
        file_menu.addAction(_t("menu_refresh"), self._refresh_all, "Ctrl+R")
        file_menu.addSeparator()
        file_menu.addAction(_t("menu_quit"), self.close, "Ctrl+Q")

        tools_menu = menubar.addMenu(_t("menu_tools"))
        tools_menu.addAction(_t("menu_scan_security"), self._run_security_scan)
        tools_menu.addAction(_t("menu_nag_me"), self._do_nag)
        tools_menu.addAction(_t("menu_hasselhoff"), self._do_hoff)

        help_menu = menubar.addMenu(_t("menu_help"))
        help_menu.addAction(_t("menu_about"), self._show_about)

    def _on_page_selected(self, key: str):
        if key in self._pages:
            self.stack.setCurrentWidget(self._pages[key])

    def _on_settings_changed(self, new_config: dict):
        from i18n import get_language
        old_lang = get_language()
        new_lang = new_config.get("general", {}).get("language", "en")

        self._config = new_config
        old_dismissed = self._alert_manager._dismissed.copy()
        old_dismiss_all = self._alert_manager._dismiss_all
        self._alert_manager = AlertManager(new_config)
        self._alert_manager._dismissed = old_dismissed
        self._alert_manager._dismiss_all = old_dismiss_all
        set_language(new_lang)
        # Propagate config to pages that use Haiku
        if hasattr(self.page_activity, 'set_config'):
            self.page_activity.set_config(new_config)
        if hasattr(self.page_health, 'set_config'):
            self.page_health.set_config(new_config)
        if hasattr(self.page_save_points, 'set_config'):
            self.page_save_points.set_config(new_config)
        if hasattr(self.page_prompt_helper, 'set_config'):
            self.page_prompt_helper.set_config(new_config)
        # Sync popup suppress to security page
        popups_off = not new_config["alerts"].get("popup_notifications", True)
        self.page_security._suppress_popups = popups_off

        self._claude_statusbar.showMessage("Settings applied", 3000)

        if old_lang != new_lang:
            reply = QMessageBox.question(
                self, _t("window_title"),
                "Language changed. Restart the app now?\n"
                "Мову змінено. Перезапустити зараз?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                import os
                import subprocess
                subprocess.Popen([sys.executable, "-m", "gui.app"])
                QApplication.instance().quit()

    def _on_project_changed(self, path: str) -> None:
        """Sync selected project to Activity, Snapshots, Health, and plugins."""
        self.page_activity.set_project_dir(path)
        self.page_save_points.set_project_dir(path)
        self.page_prompt_helper.set_project_dir(path)
        # Propagate project dir to test_runner plugin
        try:
            for p in self._plugin_registry._plugins:
                if type(p).__name__ == "TestRunnerPlugin":
                    p._project_dir = path
        except Exception:
            pass
        # Health: set dir + enable scan button + update label
        self.page_health._project_dir = path
        display = path if len(path) <= 50 else "..." + path[-47:]
        self.page_health._dir_label.setText(display)
        self.page_health._dir_label.setStyleSheet("color: #000000;")
        self.page_health._btn_scan.setEnabled(True)
        self.page_health._start_watch_observer()

    def _is_alert_enabled(self, source: str) -> bool:
        filters = self._config.get("alert_filters", {})
        return filters.get(source, True)

    def _end_startup_grace(self) -> None:
        self._startup_grace = False
        # After grace, suppress only if user disabled popups in settings
        popups_off = not self._config["alerts"].get("popup_notifications", True)
        self.page_security._suppress_popups = popups_off

    def _dismiss_all_alerts(self) -> None:
        """Suppress all alerts everywhere until restart."""
        from gui.pages.security import CriticalAlertDialog
        self._alert_manager.dismiss_all()
        CriticalAlertDialog._dismiss_all = True

    def _process_alert(self, alert: Alert) -> bool:
        """Process alert: sound always, popup only if enabled and not in grace."""
        fired = self._alert_manager.process(alert)
        if not fired:
            return False
        # No popups during startup grace period
        if self._startup_grace:
            return True
        # Popups disabled by user setting
        if not self._config["alerts"].get("popup_notifications", True):
            return True
        # In-app popup only for critical/high
        if alert.severity in ("critical", "high"):
            from gui.win95_popup import Win95Popup
            popup = Win95Popup(
                alert.title, alert.message,
                severity=alert.severity,
                auto_close_ms=0,
                parent=self,
                show_dismiss=True,
            )
            result = popup.exec_()
            if result == Win95Popup.DISMISSED:
                self._alert_manager.dismiss(alert)
            elif result == Win95Popup.DISMISSED_ALL:
                self._dismiss_all_alerts()
        return True

    def _refresh_all(self):
        if self._collecting:
            return
        self._collecting = True

        # Docker + Ports in background thread
        client = self._state.docker_client if self._state.docker_available else None
        self._collector_thread = DataCollectorThread(client, self)
        self._collector_thread.data_ready.connect(self._on_data_ready)
        self._collector_thread.finished.connect(self._collector_thread.deleteLater)
        self._collector_thread.start()

        # Claude stats
        if self._state.claude_dir:
            try:
                from core.token_parser import TokenParser
                from core.calculator import CostCalculator
                from core.usage_analyzer import Analyzer
                from core.nagger.messages import get_nag_message, get_nag_level

                parser = TokenParser()
                stats = parser.parse_today()
                calc = CostCalculator()
                cost = calc.calculate_cost(stats)
                cache_eff = Analyzer.cache_efficiency(stats)
                savings = Analyzer.cache_savings_usd(stats)
                comparison = Analyzer.model_comparison(stats)
                projects = Analyzer.project_breakdown(stats)

                level = get_nag_level(stats.total_billable)
                nag_msg = get_nag_message(level, stats.total_billable, len(stats.sessions))

                sub = parser.get_subscription()
                self.page_overview.set_subscription(sub)
                self.page_overview.update_data(
                    stats, cost, cache_eff, savings, nag_msg,
                    sub=sub, comparison=comparison, projects=projects,
                )

                if self._is_alert_enabled("usage"):
                    self._check_usage_alerts(stats, sub)

                # Save to history DB (once per refresh, upserts today's row)
                try:
                    from datetime import date
                    if self._history_db is None:
                        self._history_db = HistoryDB()
                        self._history_db.init()
                    self._history_db.save_daily_stats(
                        date=date.today().isoformat(),
                        tokens=stats.total_billable,
                        cost=cost.total_cost,
                        cache_efficiency=cache_eff,
                        sessions=len(stats.sessions),
                        security_score=self._last_security_score,
                    )
                    history = self._history_db.get_daily_stats(7)
                    self.page_overview.update_trends(history)
                except Exception as e:
                    log.error("History save error: %s", e)

            except Exception as e:
                log.error("Claude stats error: %s", e)

    def _on_data_ready(self, data: dict):
        self._collecting = False

        # Docker → compact widget on Overview
        infos = data.get("docker", [])
        self.page_overview.update_docker_compact(infos)
        if self._is_alert_enabled("docker"):
            self._check_docker_alerts(infos)

        # Ports → compact widget on Overview
        ports = data.get("ports", [])
        self.page_overview.update_ports_compact(ports)
        if self._is_alert_enabled("ports"):
            for p in ports:
                if p.get("conflict"):
                    self._process_alert(Alert(
                        source="ports", severity="warning",
                        title=f"Port {p['port']} conflict",
                        message=f"Port {p['port']} used by multiple processes",
                    ))

        # Plugin registry alerts (test_runner etc.)
        try:
            plugin_alerts = self._plugin_registry.collect_all()
            for alert in plugin_alerts:
                if self._is_alert_enabled(alert.source):
                    self._process_alert(alert)
        except Exception as e:
            log.warning("Plugin collect_all error: %s", e)

        # Activity Log — feed docker + port data
        self.page_activity.update_data(
            docker_data=infos,
            port_data=ports,
        )

        # Auto-snapshot on first data collection (app start)
        if not hasattr(self, "_start_snapshot_taken"):
            self._start_snapshot_taken = True
            self.page_save_points.take_auto_snapshot(
                label=_t("snap_start_label"),
                docker_data=infos,
                port_data=ports,
            )
            # Check for Claude Code updates — delayed to avoid startup popup spam
            QTimer.singleShot(16_000, self._check_claude_update)
            # Initial API status check
            self._check_api_status()

    def _check_docker_alerts(self, infos: list[dict]):
        """Docker alerts — no Hasselhoff, just problems."""
        cpu_thresh = self._config["plugins"]["docker_monitor"]["cpu_threshold"]
        ram_thresh = self._config["plugins"]["docker_monitor"]["ram_threshold"]

        for info in infos:
            name = info["name"]

            if info["status"] == "exited" and info.get("exit_code", 0) != 0:
                self._process_alert(Alert(
                    source="docker", severity="critical",
                    title=f"{name} crashed (exit {info['exit_code']})",
                    message=f"Container {name} exited with code {info['exit_code']}",
                ))
            elif info["status"] == "running":
                if info["cpu_percent"] > cpu_thresh:
                    self._process_alert(Alert(
                        source="docker", severity="warning",
                        title=f"{name} CPU {info['cpu_percent']:.0f}%",
                        message=f"CPU at {info['cpu_percent']:.1f}%",
                    ))
                if info["mem_limit"] > 0:
                    ram_pct = (info["mem_usage"] / info["mem_limit"]) * 100
                    if ram_pct > ram_thresh:
                        self._process_alert(Alert(
                            source="docker", severity="critical",
                            title=f"{name} RAM {ram_pct:.0f}%",
                            message=f"RAM at {ram_pct:.1f}%",
                        ))

    def _check_usage_alerts(self, stats, sub: dict):
        """Alert on high token usage — no Hasselhoff."""
        is_api = sub.get("is_paid_tokens")
        if is_api:
            return

        if stats.total_billable > 800_000:
            self._process_alert(Alert(
                source="usage", severity="warning",
                title=f"High usage: {stats.total_billable / 1_000_000:.1f}M tokens",
                message=f"You've used {stats.total_billable:,} billable tokens today. "
                        "Consider using /compact or switching to a lighter model.",
            ))
        if stats.total_billable > 2_000_000:
            self._process_alert(Alert(
                source="usage", severity="critical",
                title=f"Very high usage: {stats.total_billable / 1_000_000:.1f}M tokens!",
                message=f"Burned through {stats.total_billable:,} tokens today. "
                        "Rate limits may hit soon!",
            ))

    def _run_security_scan(self):
        self.page_security.set_scanning(True)

        def scan():
            from plugins.security_scan.scanners import (
                Finding,
                scan_docker_security, scan_env_in_git,
                scan_exposed_ports,
                scan_firewall, scan_ssh_config, scan_system_updates,
                scan_sudoers, scan_world_writable,
                scan_sentinel_processes, scan_sentinel_network,
                scan_sentinel_filesystem, scan_sentinel_cron,
                scan_container_escape, scan_supply_chain,
                scan_git_hooks, scan_env_leaks,
            )
            findings = []

            if self._state.docker_available and self._state.docker_client:
                try:
                    from plugins.docker_monitor.collector import collect_containers
                    containers = self._state.docker_client.containers.list(all=True)
                    infos = collect_containers(containers)
                    findings.extend(scan_docker_security(infos))
                except Exception as e:
                    log.warning("docker security scan in GUI skipped: %s", e)

            scan_paths = [Path(p).expanduser() for p in
                          self._config["plugins"]["security_scan"].get("scan_paths", ["~"])]
            findings.extend(scan_env_in_git(scan_paths))

            try:
                from plugins.port_map.collector import collect_ports
                ports = collect_ports()
                findings.extend(scan_exposed_ports(ports))
                # Port conflicts as security findings
                for p in ports:
                    if p.get("conflict"):
                        findings.append(Finding(
                            "network", "warning",
                            f"Port {p['port']} conflict — multiple processes listening",
                            f"port:{p['port']}",
                        ))
            except Exception as e:
                log.warning("port-map scan in GUI skipped: %s", e)

            findings.extend(scan_sentinel_processes())
            findings.extend(scan_sentinel_network())
            findings.extend(scan_sentinel_filesystem(scan_paths))
            findings.extend(scan_sentinel_cron())

            # New Phase 4 scanners
            findings.extend(scan_container_escape())
            findings.extend(scan_supply_chain(scan_paths))
            findings.extend(scan_git_hooks(scan_paths))
            findings.extend(scan_env_leaks())

            # System-level checks
            findings.extend(scan_firewall())
            findings.extend(scan_ssh_config())
            findings.extend(scan_system_updates())
            findings.extend(scan_sudoers())
            findings.extend(scan_world_writable())

            return [
                {"type": f.type, "severity": f.severity,
                 "description": f.description, "source": f.source}
                for f in findings
            ]

        if self._scan_thread and self._scan_thread.isRunning():
            return
        self._scan_thread = SecurityScanThread(scan)
        self._scan_thread.scan_done.connect(self._on_scan_done)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.start()

    def _on_scan_done(self, findings: list[dict]):
        prev_keys = getattr(self, "_prev_security_keys", set())
        curr_keys = {f"{f['type']}:{f['description']}" for f in findings}
        new_keys = curr_keys - prev_keys
        self._prev_security_keys = curr_keys

        self.page_security.update_data(findings)
        self.page_security.set_scanning(False)
        self.page_overview.update_security_score(findings)

        # Track score for history
        deductions = {"critical": 20, "high": 10, "medium": 3, "low": 1}
        total_ded = sum(deductions.get(f.get("severity", "low"), 1) for f in findings)
        self._last_security_score = max(0, 100 - total_ded)

        critical_count = self.page_security.critical_count()
        self.sidebar.update_alert("security", critical_count)

        # Win95 popups for new critical/high findings
        if self._is_alert_enabled("security"):
            for f in findings:
                key = f"{f['type']}:{f['description']}"
                if key in new_keys and f["severity"] in ("critical", "high"):
                    self._process_alert(Alert(
                        source="security", severity=f["severity"],
                        title=f"[{f['type']}] {f['description'][:50]}",
                        message=f["description"],
                    ))

    def _trigger_hasselhoff(self, message: str):
        """Hasselhoff — only from Wizard page and manual trigger."""
        try:
            from core.nagger.hasselhoff import (
                get_hoff_phrase, get_hoff_image, play_hoff, is_hoff_playing,
                stop_hoff,
            )
            if is_hoff_playing():
                stop_hoff()
                self._claude_statusbar.showMessage("HASSELHOFF: Stopped.", 3000)
                self.page_overview.btn_hoff.setText("▶ Hasselhoff")
                return

            img_path = get_hoff_image()
            if img_path:
                self.page_overview.set_hoff_image(img_path)
            song = play_hoff()
            phrase = get_hoff_phrase()
            song_name = song.stem if song else "?"
            self._claude_statusbar.showMessage(
                f"HASSELHOFF: {song_name} — {phrase}", 8000,
            )
            self.page_overview.btn_hoff.setText("⏹ Stop Hasselhoff")
        except ImportError:
            self._claude_statusbar.showMessage(f"HASSELHOFF: {message}", 5000)

    def _do_nag(self):
        self._alert_manager.play_sound(Alert(
            source="nag", severity="critical", title="Nag", message="nag",
        ))

    def _do_hoff(self):
        self._trigger_hasselhoff("Manual Hasselhoff!")

    def _check_api_status(self) -> None:
        """Check Anthropic API status in background thread."""
        if self._history_db is None:
            self._history_db = HistoryDB()
            self._history_db.init()
        if self._status_checker is None:
            self._status_checker = StatusChecker(self._history_db)

        thread = StatusCheckThread(self._status_checker, self)
        thread.done.connect(self._on_status_checked)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._status_thread = thread

    def _on_status_checked(self, result) -> None:
        """Update statusbar + overview from status check result."""
        self._claude_statusbar.update_status(
            result.api_indicator, result.claude_version, result.timestamp
        )
        if hasattr(self.page_overview, "update_claude_status"):
            history = self._status_checker.get_status_history(hours=24)
            try:
                _ensure_version_table(self._history_db)
                rows = self._history_db.execute(
                    "SELECT version, detected_at FROM claude_versions ORDER BY id DESC LIMIT 5"
                ).fetchall()
            except Exception as e:
                log.warning("claude_versions readback failed: %s", e)
                rows = []
            self.page_overview.update_claude_status(result, history, rows)

        # Connect overview Check Now button (once)
        if not hasattr(self, "_status_btn_connected"):
            if hasattr(self.page_overview, "btn_check_now"):
                self.page_overview.btn_check_now.clicked.connect(self._check_api_status)
                self._status_btn_connected = True

    def _check_claude_update(self):
        """Check if Claude Code version changed since last run."""
        try:
            if self._history_db is None:
                self._history_db = HistoryDB()
                self._history_db.init()
            update_info = check_for_update(self._history_db)
            if update_info:
                from gui.changelog_popup import ChangelogPopup
                popup = ChangelogPopup(
                    old_version=update_info["old_version"],
                    new_version=update_info["new_version"],
                    changelog_url=update_info["changelog_url"],
                    config=self._config,
                    parent=self,
                )
                popup.exec_()
                if popup.was_dismissed:
                    dismiss_version(self._history_db, update_info["new_version"])
        except Exception as e:
            log.error("Changelog check error: %s", e)

    def _auto_snapshot(self):
        """Take auto-snapshot if snapshots page has a project dir."""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M")
        self.page_save_points.take_auto_snapshot(
            label=f"{_t('snap_auto_label')} ({time_str})",
        )

    def _show_about(self):
        self._on_page_selected("about")


def main() -> None:
    """Console-script entrypoint (dev-monitor-gui)."""
    from core.autodiscovery import discover_system
    from core.config import load_config
    from gui.app.tray import MonitorTrayApp

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = load_config()
    system_state = discover_system(config.get("paths", {}))

    app = MonitorTrayApp(config, system_state)
    sys.exit(app.run())
