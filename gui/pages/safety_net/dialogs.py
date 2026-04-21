"""Modal dialogs used by SafetyNetPage — git config + file picker."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.safety_net import PickableFile
from i18n import get_string as _t


class GitConfigDialog(QDialog):
    """Dialog for git config user.name + user.email."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("safety_git_config_title"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        explain = QLabel(_t("safety_git_config_explain"))
        explain.setWordWrap(True)
        explain.setStyleSheet("padding: 8px; background: #fffff0; border: 1px solid #cccc00;")
        layout.addWidget(explain)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your Name")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        form.addRow("Name:", self.name_input)
        form.addRow("Email:", self.email_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[str, str]:
        return self.name_input.text().strip(), self.email_input.text().strip()


class PickDialog(QDialog):
    """Dialog to pick files from backup branch."""

    def __init__(self, files: list[PickableFile], backup_branch: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("safety_pick_title").format(backup_branch))
        self.setMinimumSize(600, 400)
        self._checkboxes: list[tuple[QCheckBox, str]] = []

        layout = QVBoxLayout(self)

        desc = QLabel(_t("safety_pick_desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 8px; color: #333;")
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 2px inset #808080; background: white; }")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setAlignment(Qt.AlignTop)

        status_icons = {"added": "+", "modified": "~", "deleted": "-"}
        status_colors = {"added": "#006600", "modified": "#cc6600", "deleted": "#cc0000"}

        for f in files:
            row = QHBoxLayout()
            cb = QCheckBox()
            row.addWidget(cb)
            self._checkboxes.append((cb, f.path))

            icon = status_icons.get(f.status, "?")
            color = status_colors.get(f.status, "#333")

            stat_text = f.path
            if f.status == "added":
                stat_text = f"{icon} {f.path} (NEW, {f.additions} lines)"
            elif f.status == "deleted":
                stat_text = f"{icon} {f.path} (DELETED)"
            else:
                stat_text = f"{icon} {f.path} (+{f.additions} -{f.deletions})"

            path_lbl = QLabel(stat_text)
            path_lbl.setStyleSheet(f"color: {color}; font-family: monospace;")
            row.addWidget(path_lbl)
            row.addStretch()

            wrapper = QWidget()
            wrapper.setLayout(row)
            cl.addWidget(wrapper)

            # Explanation line
            if f.explanation and f.explanation != "Project file":
                exp_lbl = QLabel(f"    {f.explanation}")
                exp_lbl.setStyleSheet("color: #808080; font-size: 11px; padding-left: 24px;")
                cl.addWidget(exp_lbl)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._btn_apply = QPushButton(_t("safety_pick_apply"))
        self._btn_apply.setStyleSheet(
            "QPushButton { background: #000080; color: white; padding: 6px 16px; "
            "border: 2px outset #4040c0; font-weight: bold; }"
        )
        self._btn_apply.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_apply)

        btn_cancel = QPushButton(_t("cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def selected_paths(self) -> list[str]:
        return [path for cb, path in self._checkboxes if cb.isChecked()]
