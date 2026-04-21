"""UI Dictionary popup — scrollable visual cheat sheet of UI elements."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QFrame, QPushButton,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from data.ui_elements import UI_ELEMENTS, UIElement, get_elements_by_category
from i18n import get_string as _t


_CATEGORY_TITLES = {
    "layout": ("Layout", "Макет"),
    "interactive": ("Interactive", "Інтерактивні"),
    "content": ("Content", "Контент"),
    "form": ("Form", "Форми"),
}


class UIDictionaryPopup(QDialog):
    def __init__(self, lang: str = "en", parent=None):
        super().__init__(parent)
        self._lang = lang
        self.setWindowTitle(_t("health_section_ui_dict"))
        self.setMinimumSize(700, 550)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(_t("health_section_ui_dict"))
        title.setFont(QFont("MS Sans Serif", 14, QFont.Bold))
        title.setStyleSheet("color: #000080;")
        layout.addWidget(title)

        desc = QLabel(_t("ui_dict_desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #333; padding: 4px 0;")
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 2px inset #808080; background: white; }")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setAlignment(Qt.AlignTop)

        by_category = get_elements_by_category()
        for cat in ["layout", "interactive", "content", "form"]:
            elements = by_category.get(cat, [])
            if not elements:
                continue

            en_title, ua_title = _CATEGORY_TITLES.get(cat, (cat, cat))
            cat_title = ua_title if self._lang == "ua" else en_title

            cat_lbl = QLabel(cat_title)
            cat_lbl.setFont(QFont("MS Sans Serif", 12, QFont.Bold))
            cat_lbl.setStyleSheet("color: #000080; padding-top: 8px;")
            cl.addWidget(cat_lbl)

            for el in elements:
                frame = self._make_element(el)
                cl.addWidget(frame)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        close_btn = QPushButton(_t("close"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _make_element(self, el: UIElement) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { border: 1px solid #d0d0d0; margin: 4px 0; "
            "padding: 8px; background: #fafafa; }"
        )
        layout = QVBoxLayout(frame)
        layout.setSpacing(4)

        # Name (always English for AI)
        name_lbl = QLabel(el.name)
        name_lbl.setFont(QFont("MS Sans Serif", 11, QFont.Bold))
        name_lbl.setStyleSheet("color: #000080;")
        layout.addWidget(name_lbl)

        # ASCII wireframe
        wire_lbl = QLabel(el.wireframe)
        wire_lbl.setFont(QFont("Courier New", 9))
        wire_lbl.setStyleSheet(
            "background: #1a1a1a; color: #00ff00; padding: 6px; "
            "font-family: 'Courier New', monospace; border: 1px solid #333;"
        )
        layout.addWidget(wire_lbl)

        # Description
        desc = el.desc_ua if self._lang == "ua" else el.desc_en
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #333; padding: 2px 0;")
        layout.addWidget(desc_lbl)

        # Prompt example
        prompt = el.prompt_ua if self._lang == "ua" else el.prompt_en
        prompt_header = "Скажи AI:" if self._lang == "ua" else "Tell AI:"
        prompt_lbl = QLabel(f'{prompt_header} "{prompt}"')
        prompt_lbl.setWordWrap(True)
        prompt_lbl.setStyleSheet(
            "color: #5500aa; font-style: italic; "
            "padding: 4px 8px; background: #f8f0ff; "
            "border: 1px solid #d0c0e0;"
        )
        layout.addWidget(prompt_lbl)

        return frame
