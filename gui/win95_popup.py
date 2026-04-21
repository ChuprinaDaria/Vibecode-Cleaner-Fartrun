"""Win95-style notification popup dialog."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

_SEVERITY_ICONS = {
    "critical": "\u2716",
    "warning": "\u26A0",
    "info": "\u2139",
}

_SEVERITY_COLORS = {
    "critical": "#cc0000",
    "warning": "#cc8800",
    "info": "#000080",
}

_SEVERITY_TITLES = {
    "critical": "Error",
    "warning": "Warning",
    "info": "Information",
}

WIN95_POPUP_STYLE = """
QDialog {
    background-color: #c0c0c0;
    border: 2px outset #dfdfdf;
}
QLabel {
    color: #000000;
}
QPushButton {
    background: #c0c0c0;
    border: 2px outset #dfdfdf;
    padding: 4px 20px;
    font-weight: bold;
    min-width: 75px;
}
QPushButton:pressed {
    border: 2px inset #808080;
}
"""


class Win95Popup(QDialog):
    """Windows 95-style message box for alerts."""

    # Result codes for dismiss actions
    DISMISSED = 2
    DISMISSED_ALL = 3

    def __init__(self, title: str, message: str, severity: str = "info",
                 auto_close_ms: int = 8000, parent=None,
                 show_dismiss: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(WIN95_POPUP_STYLE)
        self.setMinimumWidth(350)
        self.setWindowFlags(Qt.Dialog)

        layout = QVBoxLayout(self)

        # Title bar simulation
        title_bar = QLabel(f"  {_SEVERITY_TITLES.get(severity, 'Notice')}")
        title_bar.setStyleSheet(
            "background: #000080; color: white; font-weight: bold; "
            "padding: 2px 4px; font-size: 12px;"
        )
        layout.addWidget(title_bar)

        # Content area
        content_layout = QHBoxLayout()

        # Icon
        self._icon_label = QLabel(_SEVERITY_ICONS.get(severity, "\u2139"))
        self._icon_label.setFont(QFont("Arial", 32))
        self._icon_label.setStyleSheet(
            f"color: {_SEVERITY_COLORS.get(severity, '#000080')}; "
            "padding: 8px; min-width: 50px;"
        )
        self._icon_label.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        content_layout.addWidget(self._icon_label)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("padding: 8px; font-size: 12px;")
        content_layout.addWidget(msg_label, stretch=1)

        layout.addLayout(content_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if show_dismiss:
            skip_btn = QPushButton("Skip")
            skip_btn.setToolTip("Dismiss until next session")
            skip_btn.clicked.connect(lambda: self.done(self.DISMISSED))
            btn_layout.addWidget(skip_btn)

            skip_all_btn = QPushButton("Close All")
            skip_all_btn.clicked.connect(lambda: self.done(self.DISMISSED_ALL))
            btn_layout.addWidget(skip_all_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Auto-close timer
        if auto_close_ms > 0:
            QTimer.singleShot(auto_close_ms, self.accept)
