"""SnapshotsPage — environment snapshot UI.

Background Haiku thread for diff explanation lives in ``threads.py``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.history import HistoryDB
from core.models import EnvironmentSnapshot, SnapshotDiff
from core.snapshot_manager import (
    compare_snapshots, create_snapshot, delete_snapshot, load_snapshots,
)
from gui.copyable_widgets import make_copy_all_button
from gui.pages.snapshots.threads import HaikuSnapshotThread
from gui.win95 import (
    BUTTON_STYLE, ERROR, FONT_MONO, FONT_UI, GROUP_STYLE, HINT_STRIP_STYLE,
    PAGE_TITLE_STYLE, PRIMARY_BUTTON_STYLE, SHADOW, SUCCESS,
    SUCCESS_BUTTON_STYLE, TITLE_DARK, WARNING,
)
from i18n import get_language, get_string as _t

log = logging.getLogger(__name__)


class SnapshotsPage(QWidget):
    """Snapshots — save and compare environment state."""

    snapshot_taken = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._project_dir: str | None = None
        self._db: HistoryDB | None = None
        self._snapshots: list[EnvironmentSnapshot] = []
        self._checkboxes: list[tuple[QCheckBox, int]] = []
        self._config: dict = {}
        self._haiku_thread: HaikuSnapshotThread | None = None
        self._compare_group: QGroupBox | None = None
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

    def hide_save_section(self) -> None:
        """Hide internal save buttons — used when embedded under a unified save button."""
        if hasattr(self, '_btn_take'):
            self._btn_take.hide()
        if hasattr(self, '_btn_save_code'):
            self._btn_save_code.hide()

    def _get_db(self) -> HistoryDB:
        if self._db is None:
            self._db = HistoryDB()
            self._db.init()
        return self._db

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header = QHBoxLayout()
        title = QLabel(_t("snap_header"))
        title.setFont(QFont("Tahoma", 14, QFont.Bold))
        title.setStyleSheet(PAGE_TITLE_STYLE)
        header.addWidget(title)
        header.addStretch()

        self._dir_label = QLabel(_t("snap_no_dir"))
        self._dir_label.setStyleSheet(f"color: {SHADOW};")
        header.addWidget(self._dir_label)

        self._btn_select = QPushButton(_t("snap_btn_select"))
        self._btn_select.setStyleSheet(BUTTON_STYLE)
        self._btn_select.clicked.connect(self._on_select_dir)
        header.addWidget(self._btn_select)

        layout.addLayout(header)

        # Action buttons
        actions = QHBoxLayout()
        self._btn_take = QPushButton(_t("snap_btn_take"))
        self._btn_take.clicked.connect(self._on_take_snapshot)
        self._btn_take.setEnabled(False)
        self._btn_take.setStyleSheet(PRIMARY_BUTTON_STYLE)
        actions.addWidget(self._btn_take)

        self._btn_save_code = QPushButton(_t("safety_save_code_btn"))
        self._btn_save_code.setStyleSheet(SUCCESS_BUTTON_STYLE)
        self._btn_save_code.clicked.connect(self._on_save_code)
        actions.addWidget(self._btn_save_code)

        self._btn_compare = QPushButton(_t("snap_btn_compare"))
        self._btn_compare.clicked.connect(self._on_compare)
        self._btn_compare.setEnabled(False)
        self._btn_compare.setStyleSheet(BUTTON_STYLE)
        actions.addWidget(self._btn_compare)
        actions.addStretch()

        # Copy all button
        copy_btn = make_copy_all_button(self._get_all_text)
        actions.addWidget(copy_btn)

        layout.addLayout(actions)

        # Hint label — "game saves" explanation for vibe coders
        hint = QLabel(_t("snap_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STRIP_STYLE)
        layout.addWidget(hint)

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
        self._show_placeholder(_t("snap_select_dir"))

    def _get_all_text(self) -> str:
        """Collect all visible text from content area for clipboard."""
        texts = []
        for i in range(self._content_layout.count()):
            item = self._content_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                for lbl in w.findChildren(QLabel):
                    text = lbl.text().strip()
                    if text:
                        texts.append(text)
        return "\n".join(texts)

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
        self._checkboxes.clear()
        self._compare_group = None

    def _on_select_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self, _t("snap_btn_select"), str(Path.home()),
        )
        if dir_path:
            self.set_project_dir(dir_path)

    def set_project_dir(self, path: str) -> None:
        self._project_dir = path
        display = path if len(path) <= 50 else "..." + path[-47:]
        self._dir_label.setText(display)
        self._dir_label.setStyleSheet("color: #000000;")
        self._btn_take.setEnabled(True)
        self._refresh_list()

    def _on_take_snapshot(self) -> None:
        if not self._project_dir:
            return
        label, ok = QInputDialog.getText(
            self, _t("snap_btn_take"), _t("snap_label_prompt"),
        )
        if not ok:
            return
        if not label.strip():
            label = _t("snap_btn_take")

        create_snapshot(
            project_dir=self._project_dir,
            label=label.strip(),
            db=self._get_db(),
        )
        self.snapshot_taken.emit()
        self._refresh_list()

    def take_auto_snapshot(
        self,
        label: str,
        docker_data: list[dict] | None = None,
        port_data: list[dict] | None = None,
    ) -> None:
        if not self._project_dir:
            return
        create_snapshot(
            project_dir=self._project_dir,
            label=label,
            db=self._get_db(),
            docker_data=docker_data,
            port_data=port_data,
        )
        self._refresh_list()

    def _refresh_list(self) -> None:
        if not self._project_dir:
            return
        self._snapshots = load_snapshots(self._get_db(), self._project_dir)
        self._render_list()

    def _render_list(self) -> None:
        self._clear_content()

        if not self._snapshots:
            self._show_placeholder(_t("snap_no_snapshots"))
            return

        for snap in self._snapshots:
            row = self._make_snapshot_row(snap)
            self._content_layout.addWidget(row)

        self._content_layout.addStretch()

    def _make_snapshot_row(self, snap: EnvironmentSnapshot) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { border-bottom: 1px solid #e0e0e0; padding: 4px; background: white; }"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)

        cb = QCheckBox()
        cb.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(cb)
        self._checkboxes.append((cb, snap.id))

        id_lbl = QLabel(f"#{snap.id}")
        id_lbl.setStyleSheet(
            f"color: {TITLE_DARK}; font-weight: bold; font-family: {FONT_MONO};"
        )
        id_lbl.setFixedWidth(40)
        layout.addWidget(id_lbl)

        time_lbl = QLabel(snap.timestamp[:16].replace("T", " "))
        time_lbl.setStyleSheet(f"color: #333; font-family: {FONT_MONO};")
        time_lbl.setFixedWidth(130)
        layout.addWidget(time_lbl)

        # Show haiku_label if available, fallback to user label
        if snap.haiku_label:
            label_text = snap.haiku_label
            label_style = f"color: #5500aa; font-style: italic; font-family: {FONT_UI};"
        else:
            label_text = f'"{snap.label}"'
            label_style = f"color: #333; font-style: italic; font-family: {FONT_UI};"

        label_lbl = QLabel(label_text)
        label_lbl.setTextFormat(Qt.PlainText)
        label_lbl.setStyleSheet(label_style)
        layout.addWidget(label_lbl)

        layout.addStretch()

        info_parts = []
        if snap.git_branch:
            info_parts.append(snap.git_branch)
        if snap.containers:
            info_parts.append(f"{len(snap.containers)} containers")
        if snap.listening_ports:
            info_parts.append(f"{len(snap.listening_ports)} ports")
        if info_parts:
            info_lbl = QLabel(" | ".join(info_parts))
            info_lbl.setStyleSheet(f"color: {SHADOW}; font-size: 11px;")
            layout.addWidget(info_lbl)

        del_btn = QPushButton(_t("snap_btn_delete"))
        del_btn.setFixedWidth(60)
        del_btn.setStyleSheet(BUTTON_STYLE)
        del_btn.clicked.connect(lambda _, sid=snap.id: self._on_delete(sid))
        layout.addWidget(del_btn)

        return frame

    def _on_checkbox_changed(self) -> None:
        selected = [sid for cb, sid in self._checkboxes if cb.isChecked()]
        self._btn_compare.setEnabled(len(selected) == 2)

    def _on_compare(self) -> None:
        selected = [sid for cb, sid in self._checkboxes if cb.isChecked()]
        if len(selected) != 2:
            return

        snap_map = {s.id: s for s in self._snapshots}
        old_id, new_id = sorted(selected)
        old_snap = snap_map.get(old_id)
        new_snap = snap_map.get(new_id)
        if not old_snap or not new_snap:
            return

        diff = compare_snapshots(old_snap, new_snap)
        self._render_compare(old_id, new_id, diff, old_snap, new_snap)

    def _render_compare(
        self,
        old_id: int,
        new_id: int,
        diff: SnapshotDiff,
        old_snap: EnvironmentSnapshot | None = None,
        new_snap: EnvironmentSnapshot | None = None,
    ) -> None:
        # Remove previous compare results
        for i in range(self._content_layout.count() - 1, -1, -1):
            item = self._content_layout.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), "_is_compare_result"):
                item.widget().deleteLater()
                self._content_layout.removeItem(item)

        group = QGroupBox(_t("snap_compare_title").format(old_id, new_id))
        group._is_compare_result = True
        group.setStyleSheet(GROUP_STYLE)
        gl = QVBoxLayout(group)
        self._compare_group = group

        if diff.total_changes == 0:
            gl.addWidget(QLabel(f"  {_t('snap_no_changes')}"))
            self._content_layout.insertWidget(self._content_layout.count() - 1, group)
            return

        # Haiku loading placeholder — will be replaced by thread result
        self._haiku_compare_label = QLabel(_t("snap_haiku_loading"))
        self._haiku_compare_label.setStyleSheet(
            f"color: #5500aa; font-style: italic; font-size: 11px; "
            f"padding: 4px 8px; background: #f8f8ff; "
            f"border: 2px inset {SHADOW}; font-family: {FONT_UI};"
        )
        self._haiku_compare_label.setWordWrap(True)
        gl.addWidget(self._haiku_compare_label)

        # Git
        if diff.branch_changed or diff.dirty_added or diff.dirty_removed:
            gl.addWidget(self._section_label(f"\U0001f4c1 {_t('snap_git_section')}"))
            if diff.branch_changed:
                gl.addWidget(self._detail_label(
                    _t("snap_branch_changed").format(diff.old_branch, diff.new_branch)
                ))
            for f in diff.dirty_added:
                gl.addWidget(self._detail_label(f"  + {f} (new dirty)", "#006600"))
            for f in diff.dirty_removed:
                gl.addWidget(self._detail_label(f"  - {f} (cleaned)", "#006600"))

        # Docker
        if diff.containers_added or diff.containers_removed or diff.containers_status_changed:
            gl.addWidget(self._section_label(f"\U0001f433 {_t('snap_docker_section')}"))
            for c in diff.containers_added:
                gl.addWidget(self._detail_label(f"  + {c} (new)", "#006600"))
            for c in diff.containers_removed:
                gl.addWidget(self._detail_label(f"  - {c} (removed)", "#cc0000"))
            for name, old_s, new_s in diff.containers_status_changed:
                gl.addWidget(self._detail_label(f"  ~ {name}: {old_s} \u2192 {new_s}", "#cc6600"))

        # Ports
        if diff.ports_opened or diff.ports_closed:
            gl.addWidget(self._section_label(f"\U0001f50c {_t('snap_ports_section')}"))
            for p in diff.ports_opened:
                gl.addWidget(self._detail_label(f"  + :{p} (opened)", "#006600"))
            for p in diff.ports_closed:
                gl.addWidget(self._detail_label(f"  - :{p} (closed)", "#cc0000"))

        # Configs
        if diff.configs_changed or diff.configs_added or diff.configs_removed:
            gl.addWidget(self._section_label(f"\u2699\ufe0f {_t('snap_configs_section')}"))
            for c in diff.configs_changed:
                gl.addWidget(self._detail_label(f"  ~ {c} CHANGED", "#cc6600"))
            for c in diff.configs_added:
                gl.addWidget(self._detail_label(f"  + {c} (new)", "#006600"))
            for c in diff.configs_removed:
                gl.addWidget(self._detail_label(f"  - {c} (removed)", "#cc0000"))

        summary = QLabel(f"  {_t('snap_total_changes').format(diff.total_changes)}")
        summary.setStyleSheet("font-weight: bold; padding-top: 8px;")
        gl.addWidget(summary)

        self._content_layout.insertWidget(self._content_layout.count() - 1, group)

        # Trigger Haiku explanation in background
        diff_text = self._build_diff_text(diff, old_snap, new_snap)
        if diff_text and self._config.get("haiku", {}).get("api_key", ""):
            # Don't replace a still-running thread — Qt's GC would collect
            # the live QThread underneath us → segfault.
            if self._haiku_thread is not None and self._haiku_thread.isRunning():
                return
            self._haiku_thread = HaikuSnapshotThread(diff_text, self._config, on_api_error=self._haiku_error_callback, parent=self)
            self._haiku_thread.result_ready.connect(self._on_haiku_compare_ready)
            self._haiku_thread.finished.connect(self._haiku_thread.deleteLater)
            self._haiku_thread.start()
        else:
            self._haiku_compare_label.hide()

    def _build_diff_text(
        self,
        diff: SnapshotDiff,
        old_snap: EnvironmentSnapshot | None,
        new_snap: EnvironmentSnapshot | None,
    ) -> str:
        lines = []
        if old_snap and new_snap:
            lines.append(f"Before: {old_snap.label} ({old_snap.timestamp[:16]})")
            lines.append(f"After:  {new_snap.label} ({new_snap.timestamp[:16]})")
            lines.append("")
        if diff.branch_changed:
            lines.append(f"Branch changed: {diff.old_branch} -> {diff.new_branch}")
        for f in diff.dirty_added:
            lines.append(f"File became dirty: {f}")
        for f in diff.dirty_removed:
            lines.append(f"File cleaned up: {f}")
        for c in diff.containers_added:
            lines.append(f"Container added: {c}")
        for c in diff.containers_removed:
            lines.append(f"Container removed: {c}")
        for name, old_s, new_s in diff.containers_status_changed:
            lines.append(f"Container {name}: {old_s} -> {new_s}")
        for p in diff.ports_opened:
            lines.append(f"Port opened: {p}")
        for p in diff.ports_closed:
            lines.append(f"Port closed: {p}")
        for c in diff.configs_changed:
            lines.append(f"Config changed: {c}")
        for c in diff.configs_added:
            lines.append(f"Config added: {c}")
        for c in diff.configs_removed:
            lines.append(f"Config removed: {c}")
        return "\n".join(lines)

    def _on_haiku_compare_ready(self, text: str) -> None:
        if not text:
            if hasattr(self, "_haiku_compare_label"):
                self._haiku_compare_label.hide()
            return
        if hasattr(self, "_haiku_compare_label"):
            self._haiku_compare_label.setText(f"\U0001f916 {text}")

    def _on_delete(self, snapshot_id: int) -> None:
        reply = QMessageBox.question(
            self, _t("snap_btn_delete"),
            f"Delete snapshot #{snapshot_id}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            delete_snapshot(self._get_db(), snapshot_id)
            self._refresh_list()

    def _on_save_code(self) -> None:
        """Quick Save Code — delegates to Save Points page."""
        parent = self.window()
        if hasattr(parent, 'page_save_points'):
            parent.page_save_points.create_save_point_quick()

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-weight: bold; color: {TITLE_DARK}; padding-top: 4px; "
            f"font-family: {FONT_UI};"
        )
        return lbl

    @staticmethod
    def _detail_label(text: str, color: str = "#333") -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {color}; font-family: {FONT_MONO}; padding-left: 8px;"
        )
        return lbl
