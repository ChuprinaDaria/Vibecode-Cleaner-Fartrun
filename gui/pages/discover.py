"""Discover tab — resources, education, curated tools from MD files."""

from pathlib import Path

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt5.QtCore import Qt
from i18n import get_language
from core.md_fetcher import fetch_local_md, parse_resource_md, parse_education_md


def _data_dir() -> Path:
    """Find data/ directory relative to project root."""
    current = Path(__file__).resolve().parent
    for parent in [current, current.parent, current.parent.parent]:
        d = parent / "data"
        if d.is_dir():
            return d
    return current.parent.parent / "data"


class DiscoverTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        container = QWidget()
        self.items_layout = QVBoxLayout(container)
        self.items_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self._populate()

    def _populate(self):
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data_dir = _data_dir()

        # Resources
        resources_content = fetch_local_md(data_dir / "resources.md")
        if resources_content:
            sections = parse_resource_md(resources_content)
            for section in sections:
                self._add_section_header(section.title)
                for item in section.items:
                    self._add_resource_item(item.title, item.description, item.url)

        # Education
        lang = get_language()
        education_content = fetch_local_md(data_dir / "education.md")
        if education_content:
            edu = parse_education_md(education_content)
            if edu:
                self._add_section_header("Learn Security" if lang == "en" else "Вивчай безпеку")
                for category, langs in edu.items():
                    items = langs.get(lang, langs.get("en", []))
                    for item in items:
                        self._add_resource_item(
                            f"[{category}] {item.title}", item.description, item.url
                        )

        # Hooks Guide
        self._add_hooks_guide(lang)

    def _add_hooks_guide(self, lang: str) -> None:
        from i18n import get_string as _t
        if lang == "ua":
            from data.hooks_guide_ua import HOOKS_GUIDE
        else:
            from data.hooks_guide_en import HOOKS_GUIDE

        self._add_section_header(_t("hooks_guide_title"))

        desc = QLabel(_t("hooks_guide_desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #333; padding: 4px 8px;")
        self.items_layout.addWidget(desc)

        for hook in HOOKS_GUIDE:
            text = (
                f"<b>{hook['title']}</b><br/>"
                f"<i>{_t('hooks_what_happens')}</i> {hook['what_happens']}<br/>"
                f"<i>{_t('hooks_when_needed')}</i> {hook['when_you_need']}<br/>"
                f"<i>{_t('hooks_setup_file')}</i> <code>{hook['setup_file']}</code><br/>"
                f"<i>{_t('hooks_dont_forget')}</i> <code>{hook['dont_forget']}</code>"
            )
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet(
                "padding: 6px 8px; margin: 1px 4px; background: white; color: #000; "
                "border: 2px groove #808080;"
            )
            self.items_layout.addWidget(lbl)

    def _add_section_header(self, title: str):
        header = QLabel(f"<b>\u2501\u2501 {title} \u2501\u2501</b>")
        header.setStyleSheet("font-size: 14px; padding: 8px 4px 2px 4px; color: #000080;")
        self.items_layout.addWidget(header)

    def _add_resource_item(self, title: str, desc: str, url: str):
        text = (
            f'<b>{title}</b><br/>'
            f'{desc}<br/>'
            f'<a href="{url}" style="color: #000080;">{url}</a>'
        )
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setOpenExternalLinks(True)
        lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet(
            "padding: 6px 8px; margin: 1px 4px; background: white; color: #000; "
            "border: 2px groove #808080;"
        )
        self.items_layout.addWidget(lbl)

    def retranslate(self):
        self._populate()
