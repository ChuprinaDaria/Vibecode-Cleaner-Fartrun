"""Smart Rollback dialog — pick which features to keep during rollback.

Instead of asking a vibe coder to tick individual files (they don't know
what each file does), we group changed files into feature buckets via Haiku
and let them tick whole features as "keep — this worked".
"""

from __future__ import annotations

import logging

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QScrollArea, QWidget, QFrame, QDialogButtonBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from i18n import get_string as _t
from core.feature_grouper import (
    FileChange, FeatureGroup, group_files_by_feature, _fallback_group,
)

log = logging.getLogger(__name__)


class FeatureGroupingThread(QThread):
    """Group files via Haiku in background so UI doesn't freeze."""

    groups_ready = pyqtSignal(list)  # list[FeatureGroup]

    def __init__(self, files: list[FileChange], config: dict, parent=None):
        super().__init__(parent)
        self._files = files
        self._config = dict(config or {})

    def run(self):
        haiku = None
        try:
            from core.haiku_client import HaikuClient
            client = HaikuClient(config=self._config)
            if client.is_available():
                haiku = client
        except Exception as e:
            log.debug("Haiku unavailable for grouping: %s", e)

        groups = group_files_by_feature(self._files, haiku)
        self.groups_ready.emit(groups)


class SmartRollbackDialog(QDialog):
    """Pick which feature groups to keep when rolling back."""

    def __init__(self, save_point_label: str, save_point_id: int,
                 files: list[FileChange], config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("sr_title").format(save_point_id))
        self.setMinimumSize(640, 480)

        self._files = files
        self._config = config
        self._groups: list[FeatureGroup] = []
        self._checkboxes: list[tuple[QCheckBox, FeatureGroup]] = []
        self._kept_paths: list[str] = []

        layout = QVBoxLayout(self)

        # Explanation
        head = QLabel(_t("sr_explain").format(save_point_label))
        head.setWordWrap(True)
        head.setStyleSheet(
            "padding: 10px; background: #fffff0; "
            "border: 2px solid #cccc00; border-radius: 4px;"
        )
        layout.addWidget(head)

        # "Grouping in progress" placeholder
        self._loading_lbl = QLabel(_t("sr_loading"))
        self._loading_lbl.setStyleSheet("color: #808080; padding: 8px;")
        layout.addWidget(self._loading_lbl)

        # Scroll with feature checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: 2px inset #808080; background: white; }"
        )
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._content)
        layout.addWidget(scroll, 1)

        # Buttons
        btn_row = QDialogButtonBox()
        self._btn_rollback_all = btn_row.addButton(
            _t("sr_rollback_all"), QDialogButtonBox.DestructiveRole
        )
        self._btn_apply = btn_row.addButton(
            _t("sr_rollback_keep"), QDialogButtonBox.AcceptRole
        )
        self._btn_cancel = btn_row.addButton(
            _t("sr_cancel"), QDialogButtonBox.RejectRole
        )
        self._btn_rollback_all.clicked.connect(self._on_rollback_all)
        self._btn_apply.clicked.connect(self._on_apply)
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_apply.setEnabled(False)
        layout.addWidget(btn_row)

        # Start grouping in background
        self._thread = FeatureGroupingThread(files, config, self)
        self._thread.groups_ready.connect(self._on_groups_ready)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_groups_ready(self, groups: list[FeatureGroup]) -> None:
        if not groups:
            groups = _fallback_group(self._files)

        self._groups = groups
        self._loading_lbl.hide()

        for group in groups:
            frame = QFrame()
            frame.setStyleSheet(
                "QFrame { border-bottom: 1px solid #e0e0e0; padding: 6px; }"
            )
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(6, 4, 6, 4)
            fl.setSpacing(2)

            cb = QCheckBox(
                f"{group.name}  ({len(group.files)} "
                f"{_t('sr_files_suffix')})"
            )
            cb.setStyleSheet("font-weight: bold; font-size: 13px;")
            fl.addWidget(cb)

            if group.description:
                desc = QLabel(group.description)
                desc.setWordWrap(True)
                desc.setStyleSheet("color: #555; font-size: 11px; padding-left: 22px;")
                fl.addWidget(desc)

            file_lines = QLabel("\n".join(f"• {p}" for p in group.files[:8]))
            if len(group.files) > 8:
                file_lines.setText(
                    file_lines.text() + f"\n• … +{len(group.files) - 8} more"
                )
            file_lines.setStyleSheet(
                "color: #808080; font-family: monospace; "
                "font-size: 11px; padding-left: 22px;"
            )
            fl.addWidget(file_lines)

            self._content_layout.addWidget(frame)
            self._checkboxes.append((cb, group))

        self._btn_apply.setEnabled(True)

    def _on_rollback_all(self) -> None:
        """Roll back without keeping anything."""
        self._kept_paths = []
        self.accept()

    def _on_apply(self) -> None:
        kept: list[str] = []
        for cb, group in self._checkboxes:
            if cb.isChecked():
                kept.extend(group.files)
        self._kept_paths = kept
        self.accept()

    def get_kept_paths(self) -> list[str]:
        return self._kept_paths
