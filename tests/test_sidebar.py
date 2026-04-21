"""Tests for Win95 sidebar widget."""

import sys
import pytest

try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
except ImportError:
    pytest.skip("PyQt5 not available", allow_module_level=True)

from gui.sidebar import Sidebar, SidebarItem


def test_sidebar_creates_items():
    items = [
        SidebarItem("Overview", "overview"),
        SidebarItem("Docker", "docker"),
    ]
    sidebar = Sidebar(items)
    assert sidebar.count() == 2


def test_sidebar_select_item():
    items = [
        SidebarItem("Overview", "overview"),
        SidebarItem("Docker", "docker"),
    ]
    sidebar = Sidebar(items)
    sidebar.select("docker")
    assert sidebar.selected_key() == "docker"


def test_sidebar_update_counter():
    items = [SidebarItem("Docker", "docker")]
    sidebar = Sidebar(items)
    sidebar.update_counter("docker", 7)
    assert "(7)" in sidebar.item_text("docker")


def test_sidebar_update_alert():
    items = [SidebarItem("Security", "security")]
    sidebar = Sidebar(items)
    sidebar.update_alert("security", 3)
    assert "(3!)" in sidebar.item_text("security")


def test_sidebar_disable_item():
    items = [SidebarItem("Docker", "docker")]
    sidebar = Sidebar(items)
    sidebar.set_enabled("docker", False)
    assert sidebar.is_item_enabled("docker") is False
