"""Save Points — unified page for code + environment save/restore.

Three horizontal tabs — Code, Environment, Frozen files — each with its
own full-height pane so lists/tables have room to breathe. One unified
"Save before feature" button at the top records BOTH code and
environment state at once; the underlying widgets keep their own
rollback/pick/compare/delete flows.
"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout,
    QWidget,
)

from gui.pages.frozen_tab import FrozenTab
from gui.pages.safety_net import SafetyNetPage
from gui.pages.snapshots import SnapshotsPage
from gui.win95 import (
    FIELD_STYLE, HINT_STRIP_STYLE, PAGE_TITLE_STYLE, PRIMARY_BUTTON_STYLE,
    TAB_WIDGET_STYLE,
)
from i18n import get_string as _t


_TAB_HINT_STYLE = (
    "color: #333; font-size: 11px; padding: 6px 10px; "
    "background: #ffffe0; border-bottom: 1px solid #cccc00;"
)


def _tab_with_hint(hint: str | None, content: QWidget) -> QWidget:
    """Wrap a page widget with an optional yellow hint strip on top."""
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    if hint:
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(_TAB_HINT_STYLE)
        hint_lbl.setWordWrap(True)
        layout.addWidget(hint_lbl)
    layout.addWidget(content, 1)
    return wrapper


class SavePointsPage(QWidget):
    """Combined Save Points page: one save button, three stacked sections."""

    save_point_created = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._safety = SafetyNetPage()
        self._snaps = SnapshotsPage()
        self._frozen = FrozenTab()

        # Hide each embedded page's own save buttons — we replace with
        # a single unified save row at the top.
        self._safety.hide_save_section()
        self._snaps.hide_save_section()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # --- Title ---
        title = QLabel(_t("sp_header"))
        title.setFont(QFont("Tahoma", 14, QFont.Bold))
        title.setStyleSheet(PAGE_TITLE_STYLE)
        outer.addWidget(title)

        # --- Human-language hint ---
        hint = QLabel(_t("sp_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STRIP_STYLE)
        outer.addWidget(hint)

        # --- Unified save row ---
        save_row = QHBoxLayout()
        self._label_input = QLineEdit()
        self._label_input.setPlaceholderText(_t("sp_placeholder"))
        self._label_input.setStyleSheet(FIELD_STYLE)
        save_row.addWidget(self._label_input)

        self._btn_save = QPushButton(_t("sp_save_btn"))
        # Larger padding than default primary — this is the page's main action.
        self._btn_save.setStyleSheet(
            PRIMARY_BUTTON_STYLE.replace("padding: 6px 14px", "padding: 8px 20px")
        )
        self._btn_save.clicked.connect(self._on_save)
        save_row.addWidget(self._btn_save)
        outer.addLayout(save_row)

        # --- Three horizontal tabs: Code / Environment / Frozen ---
        tabs = QTabWidget()
        tabs.setStyleSheet(TAB_WIDGET_STYLE)
        tabs.setDocumentMode(False)
        tabs.addTab(
            _tab_with_hint(_t("sp_section_code_hint"), self._safety),
            _t("sp_section_code_title"),
        )
        tabs.addTab(
            _tab_with_hint(_t("sp_section_env_hint"), self._snaps),
            _t("sp_section_env_title"),
        )
        tabs.addTab(
            _tab_with_hint(_t("sp_section_frozen_hint"), self._frozen),
            _t("sp_section_frozen_title"),
        )
        outer.addWidget(tabs, 1)

    # --- Delegated setters ---

    def set_project_dir(self, path: str) -> None:
        self._project_dir = path
        self._safety.set_project_dir(path)
        self._snaps.set_project_dir(path)
        self._frozen.set_project_dir(path)

    def set_config(self, config: dict) -> None:
        self._safety.set_config(config)
        self._snaps.set_config(config)
        self._frozen.set_config(config)

    def set_haiku_error_callback(self, callback) -> None:
        if hasattr(self._safety, 'set_haiku_error_callback'):
            self._safety.set_haiku_error_callback(callback)
        if hasattr(self._snaps, 'set_haiku_error_callback'):
            self._snaps.set_haiku_error_callback(callback)

    def hide_dir_picker(self) -> None:
        self._safety.hide_dir_picker()
        self._snaps.hide_dir_picker()

    # --- Unified save ---

    def create_save_point_quick(self, label: str = "") -> None:
        """Called by other pages (Activity) to save both code + env."""
        final_label = label or _t("snap_btn_take")
        self._safety.create_save_point_quick(final_label)
        self._snaps.take_auto_snapshot(final_label)
        if hasattr(self, "_project_dir") and self._project_dir:
            self.save_point_created.emit(self._project_dir)

    def _on_save(self) -> None:
        label = self._label_input.text().strip() or _t("snap_btn_take")
        # Code save first (may show git dialogs)
        self._safety.create_save_point_quick(label)
        # Environment snapshot — always tries, never blocks
        self._snaps.take_auto_snapshot(label)
        self._label_input.clear()
        if hasattr(self, "_project_dir") and self._project_dir:
            self.save_point_created.emit(self._project_dir)

    # --- Back-compat with auto-snapshot timer in app.py ---

    def take_auto_snapshot(self, label: str,
                           docker_data=None, port_data=None) -> None:
        """Called by app's snapshot_timer — delegate to snapshot widget only."""
        self._snaps.take_auto_snapshot(label, docker_data, port_data)
