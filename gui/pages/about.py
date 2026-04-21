"""Win95-style About page with version and contacts."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QWidget,
)

from i18n import get_string as _t


VERSION = "3.0.3"

CONTACTS = [
    ("LinkedIn", "https://www.linkedin.com/in/dchuprina/"),
    ("GitHub", "https://github.com/ChuprinaDaria"),
    ("Threads", "https://www.threads.com/@sonya_orehovaya"),
    ("Email", "mailto:dchuprina@lazysoft.pl"),
    ("Reddit", "https://www.reddit.com/user/Illustrious_Grass534/"),
]


class AboutPage(QWidget):
    """Win95-styled About page for sidebar."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(40, 40, 40, 20)

        # Title
        title = QLabel("Vibecode Cleaner Fartrun\n& Awesome Hasselhoff")
        title.setFont(QFont("MS Sans Serif", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Version
        ver = QLabel(f"Version {VERSION}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setFont(QFont("MS Sans Serif", 10))
        layout.addWidget(ver)

        layout.addSpacing(12)

        # Author — bilingual
        author = QLabel(_t("about_author"))
        author.setAlignment(Qt.AlignCenter)
        author.setFont(QFont("MS Sans Serif", 10))
        author.setWordWrap(True)
        layout.addWidget(author)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        layout.addSpacing(8)

        # Contacts
        for name, url in CONTACTS:
            link = QLabel(f'<a href="{url}" style="color: #000080;">{name}</a>')
            link.setOpenExternalLinks(True)
            link.setAlignment(Qt.AlignCenter)
            layout.addWidget(link)

        layout.addStretch()
