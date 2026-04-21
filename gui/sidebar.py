"""Win95 Explorer-style sidebar widget."""

from __future__ import annotations

from dataclasses import dataclass
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QFont

from gui.win95 import ERROR, GRAY, SHADOW, TITLE_DARK


@dataclass
class SidebarItem:
    label: str
    key: str
    is_separator: bool = False


SIDEBAR_STYLE = f"""
QListWidget {{
    background: {GRAY};
    border: none;
    border-right: 2px groove {SHADOW};
    font-family: "Tahoma", "MS Sans Serif", "Liberation Sans", Arial, sans-serif;
    font-size: 12px;
    outline: none;
}}
QListWidget::item {{
    padding: 6px 10px;
    border: none;
}}
QListWidget::item:selected {{
    background: {TITLE_DARK};
    color: white;
}}
QListWidget::item:hover:!selected {{
    background: #d4d4d4;
}}
QListWidget::item:disabled {{
    color: {SHADOW};
}}
"""


class Sidebar(QListWidget):
    """Win95 Explorer sidebar with selectable items and counters."""

    page_selected = pyqtSignal(str)

    def __init__(self, items: list[SidebarItem], parent=None):
        super().__init__(parent)
        self.setFixedWidth(150)
        self.setStyleSheet(SIDEBAR_STYLE)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._items: dict[str, QListWidgetItem] = {}
        self._labels: dict[str, str] = {}
        self._counters: dict[str, str] = {}

        for item in items:
            if item.is_separator:
                list_item = QListWidgetItem("")
                list_item.setFlags(Qt.NoItemFlags)
                list_item.setSizeHint(list_item.sizeHint().__class__(0, 8))
                list_item.setBackground(QColor(GRAY))
                self.addItem(list_item)
            else:
                list_item = QListWidgetItem(item.label)
                list_item.setData(Qt.UserRole, item.key)
                self.addItem(list_item)
                self._items[item.key] = list_item
                self._labels[item.key] = item.label

        self.currentItemChanged.connect(self._on_item_changed)

        for i in range(self.count()):
            item = self.item(i)
            if item.flags() & Qt.ItemIsSelectable:
                self.setCurrentItem(item)
                break

    def _on_item_changed(self, current: QListWidgetItem, _previous):
        if current and current.data(Qt.UserRole):
            self.page_selected.emit(current.data(Qt.UserRole))

    def select(self, key: str) -> None:
        if key in self._items:
            self.setCurrentItem(self._items[key])

    def selected_key(self) -> str | None:
        current = self.currentItem()
        if current:
            return current.data(Qt.UserRole)
        return None

    def item_text(self, key: str) -> str:
        if key in self._items:
            return self._items[key].text()
        return ""

    def _update_label(self, key: str) -> None:
        if key not in self._items:
            return
        base = self._labels[key]
        counter = self._counters.get(key, "")
        text = f"{base} {counter}" if counter else base
        self._items[key].setText(text)

    def update_counter(self, key: str, count: int) -> None:
        self._counters[key] = f"({count})" if count > 0 else ""
        self._update_label(key)

    def update_alert(self, key: str, count: int) -> None:
        self._counters[key] = f"({count}!)" if count > 0 else ""
        self._update_label(key)
        if key in self._items and count > 0:
            self._items[key].setForeground(QColor(ERROR))
        elif key in self._items:
            self._items[key].setForeground(QColor("#000000"))

    def set_enabled(self, key: str, enabled: bool) -> None:
        if key in self._items:
            item = self._items[key]
            if enabled:
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            else:
                item.setFlags(Qt.NoItemFlags)

    def is_item_enabled(self, key: str) -> bool:
        if key in self._items:
            return bool(self._items[key].flags() & Qt.ItemIsEnabled)
        return False
