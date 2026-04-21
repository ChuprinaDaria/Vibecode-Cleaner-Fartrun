"""Public façade for the GUI app package.

Existing console-script entry (``dev-monitor-gui = gui.app:main``)
and ``python -m gui.app`` keep working via re-exports here.
"""
from __future__ import annotations

from gui.app.main import MonitorApp, main  # noqa: F401
from gui.app.styles import WIN95_STYLE  # noqa: F401
from gui.app.threads import DataCollectorThread, StatusCheckThread  # noqa: F401
from gui.app.tray import MonitorTrayApp, _make_tray_icon  # noqa: F401
