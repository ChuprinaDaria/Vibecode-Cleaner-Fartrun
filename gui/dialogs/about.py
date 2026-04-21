"""Win95-style About dialog with version and contacts."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QFrame,
)


VERSION = "3.0.0"

CONTACTS = [
    ("LinkedIn", "https://www.linkedin.com/in/dchuprina/"),
    ("GitHub", "https://github.com/ChuprinaDaria"),
    ("Threads", "https://www.threads.com/@sonya_orehovaya"),
    ("Email", "mailto:dchuprina@lazysoft.pl"),
    ("Reddit", "https://www.reddit.com/user/Illustrious_Grass534/"),
]


class AboutDialog(QDialog):
    """Win95-styled About Fartrun dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Fartrun")
        self.setFixedSize(380, 340)
        self.setStyleSheet(
            "QDialog { background: #c0c0c0; }"
            "QLabel { color: #000000; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 16)

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

        # Author
        author = QLabel("Зроблено Дарією Чупріною\nбо вона може \U0001f47e")
        author.setAlignment(Qt.AlignCenter)
        author.setFont(QFont("MS Sans Serif", 10))
        layout.addWidget(author)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # Contacts
        for name, url in CONTACTS:
            link = QLabel(f'<a href="{url}" style="color: #000080;">{name}</a>')
            link.setOpenExternalLinks(True)
            link.setAlignment(Qt.AlignCenter)
            layout.addWidget(link)

        layout.addStretch()

        # OK button
        btn = QPushButton("OK")
        btn.setFixedWidth(80)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignCenter)
