"""System-tray entrypoint that hosts ``MonitorApp`` plus a tray menu."""
from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.autodiscovery import SystemState
from i18n import get_string as _t


def _make_tray_icon(color: str = "green") -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    colors = {
        "green": QColor(0, 200, 0),
        "yellow": QColor(255, 200, 0),
        "red": QColor(255, 50, 50),
    }
    painter.setBrush(colors.get(color, colors["green"]))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Arial", 14, QFont.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "M")
    painter.end()
    return QIcon(pixmap)


class MonitorTrayApp:
    """System tray application wrapping MonitorApp."""

    def __init__(self, config: dict, system_state: SystemState):
        # Late import: tray.py must not pull MonitorApp at module load
        # because main.py imports tray for re-exports.
        from gui.app.main import MonitorApp

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.dashboard = MonitorApp(config, system_state)

        self.tray = QSystemTrayIcon(_make_tray_icon("green"), self.app)
        self.tray.setToolTip("Claude Monitor")
        self.tray.activated.connect(self._on_tray_click)

        self.menu = QMenu()
        self.menu.addAction("Show Dashboard", self._show)
        self.menu.addAction(_t("menu_nag_me"), self.dashboard._do_nag)
        self.menu.addAction(_t("menu_hasselhoff"), self.dashboard._do_hoff)
        self.menu.addSeparator()
        self.menu.addAction("Quit", self._quit)
        self.tray.setContextMenu(self.menu)

        self.tray.show()
        self.dashboard.show()

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show()

    def _show(self):
        self.dashboard.show()
        self.dashboard.raise_()

    def _quit(self):
        self.tray.hide()
        self.app.quit()

    def run(self):
        return self.app.exec_()
