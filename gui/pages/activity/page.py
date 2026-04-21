"""ActivityPage — timeline UI for the Activity Log feature.

Background Haiku threads live in ``threads.py``; this file is the
QWidget composition + signal wiring + render logic.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from core.activity_tracker import ActivityTracker, serialize_activity
from core.models import ActivityEntry, DockerChange, FileChange, PortChange
from core.prompt_parser import (
    UserPrompt, format_prompts_for_haiku, get_recent_prompts,
)
from gui.copyable_widgets import make_copy_all_button
from gui.pages.activity.threads import HaikuContextThread, HaikuPromptsThread
from gui.win95 import (
    BUTTON_STYLE, ERROR, FONT_MONO, FONT_UI, GRAY, GROUP_STYLE, HIGHLIGHT,
    HINT_BG, NOTIFICATION_BG, NOTIFICATION_BORDER, PAGE_TITLE_STYLE,
    SECTION_HEADER_STYLE, SHADOW, SUCCESS, SUCCESS_BUTTON_STYLE, TITLE_DARK,
    WARNING, WINDOW_BG,
)
from i18n import get_string as _t

log = logging.getLogger(__name__)


class _NestedTextEdit(QTextEdit):
    """QTextEdit that scrolls internally but forwards wheel events to the
    parent QScrollArea when it reaches the top/bottom edge."""

    def wheelEvent(self, event):
        sb = self.verticalScrollBar()
        at_top = sb.value() <= sb.minimum()
        at_bottom = sb.value() >= sb.maximum()
        scrolling_up = event.angleDelta().y() > 0
        scrolling_down = event.angleDelta().y() < 0

        if (at_top and scrolling_up) or (at_bottom and scrolling_down) or (at_top and at_bottom):
            # Forward to parent QScrollArea
            parent = self.parent()
            while parent is not None:
                if isinstance(parent, QScrollArea):
                    QApplication.sendEvent(parent.verticalScrollBar(), event)
                    return
                parent = parent.parent()
        super().wheelEvent(event)


class ActivityPage(QWidget):
    """Activity Log — timeline with 'where you stopped' block and history."""

    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._project_dir: str | None = None
        self._tracker: ActivityTracker | None = None
        self._config: dict = {}
        self._haiku_thread: HaikuContextThread | None = None
        self._prompts_thread: HaikuPromptsThread | None = None
        self._all_texts: list[str] = []
        self._where_stopped_label: QLabel | None = None
        self._last_haiku_context: str = ""
        self._last_entry_hash: str = ""
        self._db = None
        self._build_ui()

    _haiku_error_callback = None

    def set_haiku_error_callback(self, callback) -> None:
        """Set callback invoked when HaikuClient hits an API error."""
        self._haiku_error_callback = callback

    def set_config(self, config: dict) -> None:
        """Receive config (including Haiku API key)."""
        self._config = config

    def hide_dir_picker(self) -> None:
        """Hide per-page dir picker when shared project selector is active."""
        if hasattr(self, '_btn_select'):
            self._btn_select.hide()
        if hasattr(self, '_dir_label'):
            self._dir_label.hide()

    def _get_db(self):
        if self._db is None:
            from core.history import HistoryDB
            self._db = HistoryDB()
            self._db.init()
        return self._db

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header row: title + refresh + copy all
        header = QHBoxLayout()
        title = QLabel(_t("activity_header"))
        title.setFont(QFont("Tahoma", 14, QFont.Bold))
        title.setStyleSheet(PAGE_TITLE_STYLE)
        header.addWidget(title)
        header.addStretch()

        copy_btn = make_copy_all_button(lambda: "\n".join(self._all_texts))
        header.addWidget(copy_btn)

        self._btn_save_point = QPushButton(_t("safety_save_btn"))
        self._btn_save_point.setStyleSheet(SUCCESS_BUTTON_STYLE)
        self._btn_save_point.clicked.connect(self._on_save_point)
        header.addWidget(self._btn_save_point)

        self._btn_refresh = QPushButton(_t("activity_btn_refresh"))
        self._btn_refresh.setStyleSheet(BUTTON_STYLE)
        self._btn_refresh.clicked.connect(self._on_refresh)
        header.addWidget(self._btn_refresh)

        layout.addLayout(header)

        # Scrollable content area — sunken window like a classic list view.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 2px inset {SHADOW}; "
            f"background: {WINDOW_BG}; }}"
        )

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._content_widget)

        layout.addWidget(scroll)

        # Initial state
        self._show_placeholder(_t("activity_select_dir"))

    def _show_placeholder(self, text: str) -> None:
        self._clear_content()
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {SHADOW}; font-size: 14px; padding: 40px; "
            f"font-family: {FONT_UI};"
        )
        self._content_layout.addWidget(lbl)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._all_texts = []
        self._where_stopped_label = None

    def set_project_dir(self, path: str) -> None:
        """Set project directory — called from shared project selector."""
        self._project_dir = path
        self._tracker = ActivityTracker(path)
        self._on_refresh()

    def _on_refresh(self) -> None:
        if not self._tracker or not self._project_dir:
            self._show_placeholder(_t("activity_select_dir"))
            return

        if shutil.which("git") is None:
            self._show_placeholder(_t("activity_git_not_found"))
            return

        self.refresh_requested.emit()

    def update_data(
        self,
        entry: ActivityEntry | None = None,
        docker_data: list[dict] | None = None,
        port_data: list[dict] | None = None,
    ) -> None:
        """Update page with fresh activity data. Compatible with app.py call signature."""
        if not self._tracker:
            return

        if entry is None:
            entry = self._tracker.collect_activity(
                docker_containers=docker_data,
                ports=port_data,
            )

        self._render_activity(entry)

        # Restore cached Haiku context immediately (before new thread finishes)
        if self._last_haiku_context and self._where_stopped_label:
            self._where_stopped_label.setPlainText(self._last_haiku_context)
            self._where_stopped_label.setStyleSheet(
                f"QTextEdit {{ color: black; font-size: 12px; padding: 8px; "
                f"font-family: {FONT_UI}; background: transparent; border: none; }}"
            )

        # Save to SQLite
        try:
            db = self._get_db()
            entry_json = serialize_activity(entry)
            db.save_activity(
                project_dir=entry.project_dir or self._project_dir or "",
                timestamp=entry.timestamp,
                entry_json=entry_json,
            )
        except Exception as e:
            log.error("Activity log save error: %s", e)

        # Trigger Haiku only when data actually changed
        entry_hash = self._hash_entry(entry)
        if entry_hash != self._last_entry_hash:
            self._last_entry_hash = entry_hash
            self._last_haiku_context = ""
            self._start_haiku_thread(entry)

    @staticmethod
    def _hash_entry(entry: ActivityEntry) -> str:
        parts = sorted(f.path for f in entry.files)
        parts += sorted(c for c in entry.commits)
        parts += sorted(f"{d.name}:{d.status}" for d in entry.docker_changes)
        return "|".join(parts)

    def _start_haiku_thread(self, entry: ActivityEntry) -> None:
        # The previous QThread may have already been deleteLater()'d —
        # isRunning() would then raise RuntimeError on the dead
        # wrapper. Wrap in try/except and treat a dead reference as
        # "not running".
        try:
            busy = self._haiku_thread is not None and self._haiku_thread.isRunning()
        except RuntimeError:
            busy = False
        if busy:
            return

        self._haiku_thread = HaikuContextThread(entry, self._config, on_api_error=self._haiku_error_callback, parent=self)
        self._haiku_thread.result_ready.connect(self._on_haiku_ready)
        self._haiku_thread.finished.connect(self._haiku_thread.deleteLater)
        # Drop our Python reference once the C++ object is gone so the
        # next call doesn't poke at a deleted QThread.
        self._haiku_thread.finished.connect(
            lambda: setattr(self, "_haiku_thread", None)
        )
        self._haiku_thread.start()

    def _on_haiku_ready(self, haiku_context: str, haiku_summary: str) -> None:
        """Update 'where you stopped' block with Haiku response."""
        if self._where_stopped_label is None:
            return

        if not haiku_context:
            self._where_stopped_label.setPlainText(_t("activity_haiku_unavailable"))
            self._where_stopped_label.setStyleSheet(
                f"QTextEdit {{ color: {SHADOW}; font-size: 11px; padding: 8px; "
                f"font-style: italic; font-family: {FONT_UI}; "
                f"background: transparent; border: none; }}"
            )
            return

        if haiku_context:
            self._last_haiku_context = haiku_context
            self._where_stopped_label.setPlainText(haiku_context)
            self._where_stopped_label.setStyleSheet(
                f"QTextEdit {{ color: black; font-size: 12px; padding: 8px; "
                f"font-family: {FONT_UI}; background: transparent; border: none; }}"
            )
            # Update texts for copy-all
            if haiku_context not in self._all_texts:
                self._all_texts.insert(0, haiku_context)

            # Save haiku context to last activity_log row
            try:
                db = self._get_db()
                if self._project_dir:
                    rows = db.get_activity_log(self._project_dir, limit=1)
                    if rows:
                        db.execute(
                            "UPDATE activity_log SET haiku_context=?, haiku_summary=? WHERE id=?",
                            (haiku_context, haiku_summary, rows[0]["id"]),
                        )
                        db.commit()
            except Exception as e:
                log.error("Haiku context save error: %s", e)

    def _render_activity(self, entry: ActivityEntry) -> None:
        """Render activity entry into the content area with timeline style."""
        self._clear_content()

        has_content = bool(
            entry.files or entry.docker_changes
            or entry.port_changes or entry.commits
        )

        # --- "Where you stopped" — Win95 "Tip of the Day" framed panel ---
        # Title bar (gradient) + yellow notepad body, outset bevel like a
        # small dialog window.
        where_box = QFrame()
        where_box.setStyleSheet(
            f"QFrame {{ border: 2px outset {GRAY}; "
            f"background: {NOTIFICATION_BG}; margin-bottom: 4px; }}"
        )
        where_layout = QVBoxLayout(where_box)
        where_layout.setContentsMargins(0, 0, 0, 0)
        where_layout.setSpacing(0)

        where_title = QLabel(_t("activity_where_stopped"))
        where_title.setStyleSheet(SECTION_HEADER_STYLE)
        where_layout.addWidget(where_title)

        self._where_stopped_label = _NestedTextEdit()
        self._where_stopped_label.setReadOnly(True)
        self._where_stopped_label.setPlainText(_t("activity_haiku_loading"))
        self._where_stopped_label.setStyleSheet(
            f"QTextEdit {{ color: {SHADOW}; font-size: 12px; padding: 8px; "
            f"font-style: italic; font-family: {FONT_UI}; "
            f"background: transparent; border: none; }}"
        )
        self._where_stopped_label.setMinimumHeight(60)
        self._where_stopped_label.setMaximumHeight(250)
        where_layout.addWidget(self._where_stopped_label)

        self._content_layout.addWidget(where_box)
        self._all_texts.append(_t("activity_where_stopped"))

        # --- What you asked Claude ---
        self._render_prompts_section()

        if not self._tracker or not self._tracker.is_git_repo():
            self._where_stopped_label.setPlainText(_t("activity_no_git"))
            self._content_layout.addStretch()
            return

        if not has_content:
            self._where_stopped_label.setPlainText(_t("activity_no_changes"))
            # Still show recent commits even with no uncommitted changes
            commits = self._tracker.get_recent_commits(limit=10)
            if commits:
                group = self._make_group(f"{_t('activity_commits_header')} ({len(commits)})")
                group_layout = group.layout()
                for commit in commits:
                    lbl = QLabel(f"  {commit}")
                    lbl.setStyleSheet(
                        f"font-family: {FONT_MONO}; color: black; "
                        f"font-size: 11px;"
                    )
                    group_layout.addWidget(lbl)
                    self._all_texts.append(f"  {commit}")
                self._content_layout.addWidget(group)
            self._content_layout.addStretch()
            return

        # --- Timeline header ---
        ts = entry.timestamp
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%H:%M")
            date_str = _t("activity_today")
        except ValueError:
            time_str = ts
            date_str = ""

        # Title bar strip separates each timeline section like a dialog
        # title — full Win95 gradient, bold white Tahoma.
        ts_label = QLabel(f"{date_str}, {time_str}" if date_str else time_str)
        ts_label.setStyleSheet(SECTION_HEADER_STYLE)
        self._content_layout.addWidget(ts_label)
        self._all_texts.append(ts_label.text())

        # Git files
        if entry.files:
            group = self._make_group(
                f"{_t('activity_files_header')} ({len(entry.files)})"
            )
            self._all_texts.append(f"{_t('activity_files_header')} ({len(entry.files)})")
            group_layout = group.layout()
            for fc in entry.files:
                row = self._make_file_row(fc)
                group_layout.addWidget(row)
                self._all_texts.append(f"{fc.status} {fc.path} {fc.explanation}")
            self._content_layout.addWidget(group)

        # Docker changes
        if entry.docker_changes:
            group = self._make_group(_t("activity_docker_header"))
            self._all_texts.append(_t("activity_docker_header"))
            group_layout = group.layout()
            for dc in entry.docker_changes:
                row = self._make_docker_row(dc)
                group_layout.addWidget(row)
                self._all_texts.append(f"{dc.name} ({dc.status}) {dc.explanation}")
            self._content_layout.addWidget(group)

        # Port changes
        if entry.port_changes:
            group = self._make_group(_t("activity_ports_header"))
            self._all_texts.append(_t("activity_ports_header"))
            group_layout = group.layout()
            for pc in entry.port_changes:
                row = self._make_port_row(pc)
                group_layout.addWidget(row)
                self._all_texts.append(f":{pc.port} {pc.status} {pc.explanation}")
            self._content_layout.addWidget(group)

        # Recent commits
        if entry.commits:
            group = self._make_group(_t("activity_commits_header"))
            self._all_texts.append(_t("activity_commits_header"))
            group_layout = group.layout()
            for commit in entry.commits:
                lbl = QLabel(f"  {commit}")
                lbl.setStyleSheet(
                    f"font-family: {FONT_MONO}; color: black; font-size: 11px;"
                )
                group_layout.addWidget(lbl)
                self._all_texts.append(commit)
            self._content_layout.addWidget(group)

        self._content_layout.addStretch()

    def _render_prompts_section(self) -> None:
        """Add 'What you asked Claude' box with prompt list + Analyze button."""
        if not self._project_dir:
            return

        prompts = get_recent_prompts(self._project_dir, limit=10)

        # Win95 property-sheet style: outset bevel frame with a blue
        # gradient title strip + white list body.
        box = QFrame()
        box.setStyleSheet(
            f"QFrame {{ border: 2px outset {GRAY}; "
            f"background: {GRAY}; margin-top: 4px; margin-bottom: 4px; }}"
        )
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        title = QLabel(_t("prompts_header").format(len(prompts)))
        title.setStyleSheet(SECTION_HEADER_STYLE)
        bl.addWidget(title)
        self._all_texts.append(title.text())

        # Inner white list pane — sunken like a classic details view.
        body = QFrame()
        body.setStyleSheet(
            f"QFrame {{ background: {WINDOW_BG}; "
            f"border: 2px inset {SHADOW}; margin: 4px; }}"
        )
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(6, 6, 6, 6)
        body_layout.setSpacing(2)
        bl.addWidget(body)

        if not prompts:
            empty = QLabel(_t("prompts_empty"))
            empty.setStyleSheet(
                f"color: {SHADOW}; font-size: 11px; padding: 4px; "
                f"font-family: {FONT_UI};"
            )
            body_layout.addWidget(empty)
        else:
            for p in prompts:
                ts = p.timestamp[5:16].replace("T", " ") if p.timestamp else "?"
                line = QLabel(f"[{ts}] {p.short}")
                line.setWordWrap(True)
                line.setStyleSheet(
                    f"font-family: {FONT_MONO}; font-size: 11px; "
                    f"padding: 2px 4px; color: black; "
                    f"border-bottom: 1px dotted {GRAY};"
                )
                body_layout.addWidget(line)
                self._all_texts.append(line.text())

            # Analyze button + placeholder for haiku summary — live in
            # a footer row inside the framed panel, aligned right like a
            # Win95 dialog button strip.
            footer = QHBoxLayout()
            footer.setContentsMargins(6, 2, 6, 6)
            footer.addStretch()
            self._analyze_btn = QPushButton(_t("prompts_analyze_btn"))
            self._analyze_btn.setStyleSheet(BUTTON_STYLE)
            self._analyze_btn.clicked.connect(
                lambda: self._on_analyze_prompts(prompts)
            )
            footer.addWidget(self._analyze_btn)
            bl.addLayout(footer)

            self._analyze_label = QLabel("")
            self._analyze_label.setWordWrap(True)
            self._analyze_label.setStyleSheet(
                f"color: black; font-size: 12px; padding: 6px; "
                f"background: {WINDOW_BG}; border: 2px inset {SHADOW}; "
                f"font-family: {FONT_UI}; margin: 0 4px 4px 4px;"
            )
            self._analyze_label.hide()
            bl.addWidget(self._analyze_label)

        self._content_layout.addWidget(box)

    def _on_analyze_prompts(self, prompts: list[UserPrompt]) -> None:
        if not prompts:
            return

        # Defence in depth — button is disabled while running but a
        # programmatic call could still race in. The QThread may also
        # already be deleteLater()'d; treat a dead wrapper as "idle".
        try:
            busy = (
                self._prompts_thread is not None
                and self._prompts_thread.isRunning()
            )
        except RuntimeError:
            busy = False
        if busy:
            return

        # Quick pre-check: if no API key, tell the user why nothing happens
        from core.haiku_client import HaikuClient
        client = HaikuClient(config=self._config)
        if not client.is_available():
            self._analyze_label.setText(_t("prompts_analyze_unavailable"))
            self._analyze_label.setStyleSheet(
                f"color: #806600; font-size: 12px; padding: 6px; "
                f"background: {HINT_BG}; border: 2px solid {NOTIFICATION_BORDER}; "
                f"font-family: {FONT_UI}; margin: 0 4px 4px 4px;"
            )
            self._analyze_label.show()
            return

        self._analyze_label.setText(_t("prompts_analyze_loading"))
        self._analyze_label.setStyleSheet(
            f"color: {SHADOW}; font-size: 12px; padding: 6px; "
            f"background: {WINDOW_BG}; border: 2px inset {SHADOW}; "
            f"font-style: italic; font-family: {FONT_UI}; "
            f"margin: 0 4px 4px 4px;"
        )
        self._analyze_label.show()
        self._analyze_btn.setEnabled(False)

        text = format_prompts_for_haiku(prompts)
        self._prompts_thread = HaikuPromptsThread(
            text, self._config,
            on_api_error=self._haiku_error_callback, parent=self,
        )
        self._prompts_thread.result_ready.connect(self._on_prompts_analyzed)
        self._prompts_thread.finished.connect(
            lambda: self._analyze_btn.setEnabled(True)
        )
        self._prompts_thread.finished.connect(self._prompts_thread.deleteLater)
        self._prompts_thread.finished.connect(
            lambda: setattr(self, "_prompts_thread", None)
        )
        self._prompts_thread.start()

    def _on_prompts_analyzed(self, summary: str) -> None:
        if not summary:
            self._analyze_label.setText(_t("prompts_analyze_unavailable"))
            return
        self._analyze_label.setText(summary)
        self._analyze_label.setStyleSheet(
            f"color: black; font-size: 12px; padding: 6px; "
            f"background: {WINDOW_BG}; border: 2px inset {SHADOW}; "
            f"font-family: {FONT_UI}; margin: 0 4px 4px 4px;"
        )
        if summary not in self._all_texts:
            self._all_texts.append(summary)

    def _make_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(GROUP_STYLE)
        layout = QVBoxLayout(group)
        layout.setSpacing(2)
        return group

    def _make_file_row(self, fc: FileChange) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ border-bottom: 1px solid {GRAY}; "
            f"border-top: 1px solid {HIGHLIGHT}; padding: 4px; "
            f"background: {WINDOW_BG}; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        top = QHBoxLayout()

        status_map = {
            "added": ("+", SUCCESS, _t("activity_file_added")),
            "modified": ("~", TITLE_DARK, _t("activity_file_modified")),
            "deleted": ("-", ERROR, _t("activity_file_deleted")),
            "renamed": ("R", WARNING, _t("activity_file_renamed")),
        }
        icon, color, label = status_map.get(fc.status, ("?", SHADOW, fc.status))

        status_lbl = QLabel(icon)
        status_lbl.setFixedWidth(16)
        status_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-family: {FONT_MONO};"
        )
        top.addWidget(status_lbl)

        path_lbl = QLabel(fc.path)
        path_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        top.addWidget(path_lbl)

        if fc.status in ("added", "deleted"):
            tag = QLabel(f"({label})")
            tag.setStyleSheet(f"color: {color}; font-weight: bold;")
            top.addWidget(tag)

        top.addStretch()

        if fc.additions or fc.deletions:
            stats_parts = []
            if fc.additions:
                stats_parts.append(f"+{fc.additions}")
            if fc.deletions:
                stats_parts.append(f"-{fc.deletions}")
            stats_lbl = QLabel(" ".join(stats_parts))
            stats_lbl.setStyleSheet(
                f"color: {SHADOW}; font-family: {FONT_MONO}; font-size: 11px;"
            )
            top.addWidget(stats_lbl)

        layout.addLayout(top)

        if fc.explanation:
            is_env = ".env" in fc.path.lower()
            expl_color = WARNING if is_env else SHADOW
            prefix = "\u26a0\ufe0f " if is_env else "  "
            expl_text = _t("activity_env_warning") if is_env else fc.explanation

            expl_lbl = QLabel(f"{prefix}{expl_text}")
            expl_lbl.setStyleSheet(
                f"color: {expl_color}; font-size: 11px; font-family: {FONT_UI};"
            )
            layout.addWidget(expl_lbl)

        return frame

    def _make_docker_row(self, dc: DockerChange) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ border-bottom: 1px solid {GRAY}; "
            f"border-top: 1px solid {HIGHLIGHT}; padding: 4px; "
            f"background: {WINDOW_BG}; }}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)

        status_styles = {
            "new": ("+", SUCCESS),
            "removed": ("-", ERROR),
            "crashed": ("\u25cf", ERROR),
            "restarted": ("\u25cf", WARNING),
        }
        icon, color = status_styles.get(dc.status, ("?", SHADOW))

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(20)
        icon_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(dc.name)
        name_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(name_lbl)

        if dc.image:
            img_lbl = QLabel(f"({dc.image})")
            img_lbl.setStyleSheet(f"color: {SHADOW};")
            layout.addWidget(img_lbl)

        layout.addStretch()

        status_text = {
            "new": _t("activity_docker_new"),
            "removed": _t("activity_docker_removed"),
            "crashed": _t("activity_docker_crashed"),
            "restarted": _t("activity_docker_restarted"),
        }.get(dc.status, dc.status)

        status_tag = QLabel(status_text)
        status_tag.setStyleSheet(
            f"color: {color}; font-weight: bold; "
            f"border: 2px outset {GRAY}; padding: 1px 6px; "
            f"background: {GRAY}; font-family: {FONT_UI};"
        )
        layout.addWidget(status_tag)

        if dc.explanation:
            expl = QLabel(dc.explanation)
            expl.setStyleSheet(f"color: {SHADOW}; font-size: 11px;")
            layout.addWidget(expl)

        return frame

    def _make_port_row(self, pc: PortChange) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ border-bottom: 1px solid {GRAY}; "
            f"border-top: 1px solid {HIGHLIGHT}; padding: 4px; "
            f"background: {WINDOW_BG}; }}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)

        is_new = pc.status == "new"
        color = SUCCESS if is_new else ERROR
        icon = "+" if is_new else "-"

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(16)
        icon_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-family: {FONT_MONO};"
        )
        layout.addWidget(icon_lbl)

        port_lbl = QLabel(f":{pc.port}")
        port_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-family: {FONT_MONO};"
        )
        layout.addWidget(port_lbl)

        if pc.process:
            proc_lbl = QLabel(f"({pc.process})")
            proc_lbl.setStyleSheet(f"color: {SHADOW};")
            layout.addWidget(proc_lbl)

        layout.addStretch()

        tag_text = _t("activity_port_new") if is_new else _t("activity_port_closed")
        tag = QLabel(tag_text)
        tag.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(tag)

        if pc.explanation:
            expl = QLabel(pc.explanation)
            expl.setStyleSheet(f"color: {SHADOW}; font-size: 11px;")
            layout.addWidget(expl)

        return frame

    def _on_save_point(self) -> None:
        """Quick Save Point — delegates to Safety Net page if available."""
        parent = self.window()
        if hasattr(parent, 'page_save_points'):
            parent.page_save_points.create_save_point_quick()
            self._btn_save_point.setText("Saved!")
            # Briefly show a brighter green, then revert to standard success.
            self._btn_save_point.setStyleSheet(
                SUCCESS_BUTTON_STYLE.replace(SUCCESS, "#008800")
            )
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(2000, lambda: (
                self._btn_save_point.setText(_t("safety_save_btn")),
                self._btn_save_point.setStyleSheet(SUCCESS_BUTTON_STYLE),
            ))
