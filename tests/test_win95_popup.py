"""Tests for Win95 popup."""

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication
import sys

app = QApplication.instance() or QApplication(sys.argv)


def test_popup_creates_with_severity():
    from gui.win95_popup import Win95Popup
    popup = Win95Popup("Test Title", "Test message", severity="warning")
    assert popup.windowTitle() == "Test Title"
    popup.close()


def test_popup_severity_icon():
    from gui.win95_popup import Win95Popup
    for sev in ("critical", "warning", "info"):
        popup = Win95Popup("T", "M", severity=sev)
        assert popup._icon_label.text() != ""
        popup.close()


def test_popup_default_info():
    from gui.win95_popup import Win95Popup
    popup = Win95Popup("T", "M")
    assert popup._icon_label.text() == "\u2139"
    popup.close()
