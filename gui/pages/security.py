"""Security page — findings table with detail panel and human explanations."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QGroupBox, QTextEdit, QSplitter,
    QDialog,
)
from gui.copyable_table import CopyableTableWidget
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QColor

from gui.security_explanations import get_explanation, get_human_description, get_course_link
from gui.win95 import (
    BUTTON_STYLE, DANGER_BUTTON_STYLE, ERROR, FIELD_STYLE, FONT_MONO, FONT_UI,
    GRAY, GROUP_STYLE, LIST_STYLE, PAGE_TITLE_STYLE, PRIMARY_BUTTON_STYLE,
    SHADOW, SUCCESS, TITLE_BAR_GRADIENT, TITLE_DARK, WARNING, WINDOW_BG,
)
from i18n import get_string as _t


SEVERITY_COLORS = {
    "critical": ("#ffffff", "#cc0000"),
    "high": ("#000000", "#ff8c00"),
    "medium": ("#000000", "#ffcc00"),
    "low": ("#000000", "#c0c0c0"),
}


class CriticalAlertDialog(QDialog):
    _shown_findings: set[str] = set()
    _dismiss_all: bool = False  # suppress all until restart

    DISMISSED = 2
    DISMISSED_ALL = 3

    def __init__(self, finding: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("hasselhoff_angry"))
        self.setModal(True)
        self.setMinimumWidth(560)
        # Win95 system-error dialog: gray chrome + outset bevel.
        self.setStyleSheet(
            f"QDialog {{ background: {GRAY}; "
            f"border: 2px outset {GRAY}; font-family: {FONT_UI}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header — red title bar (one of the rare non-navy Win95 titles,
        # used for critical system-error dialogs).
        header = QLabel(f'STOP! {_t("hasselhoff_angry")}')
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            f"background: {ERROR}; color: white; padding: 6px 10px; "
            f"font-weight: bold; font-size: 13px; font-family: {FONT_UI};"
        )
        layout.addWidget(header)

        # Finding description — inset white field, red text.
        desc_text = finding.get("description", "")
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            f"font-size: 12px; color: {ERROR}; background: {WINDOW_BG}; "
            f"border: 2px inset {SHADOW}; padding: 6px; font-family: {FONT_UI};"
        )
        layout.addWidget(desc_label)

        explanation = get_explanation(finding.get("type", ""), desc_text)

        # What is this
        what_title = QLabel(_t("what_is_this"))
        what_title.setStyleSheet(
            f"font-weight: bold; color: black; font-family: {FONT_UI};"
        )
        layout.addWidget(what_title)
        what_label = QLabel(explanation.get("what", ""))
        what_label.setWordWrap(True)
        what_label.setStyleSheet(
            f"color: #333; padding: 2px 8px; font-family: {FONT_UI};"
        )
        layout.addWidget(what_label)

        # Risk
        risk_title = QLabel(_t("risk"))
        risk_title.setStyleSheet(
            f"font-weight: bold; color: {ERROR}; font-family: {FONT_UI};"
        )
        layout.addWidget(risk_title)
        risk_label = QLabel(explanation.get("risk", ""))
        risk_label.setWordWrap(True)
        risk_label.setStyleSheet(
            f"color: {ERROR}; padding: 2px 8px; font-family: {FONT_UI};"
        )
        layout.addWidget(risk_label)

        # How to fix — monospace code block on white, inset bevel (Win95 DOS-ish).
        fix_title = QLabel(_t("how_to_fix"))
        fix_title.setStyleSheet(
            f"font-weight: bold; color: {SUCCESS}; font-family: {FONT_UI};"
        )
        layout.addWidget(fix_title)
        fix_edit = QTextEdit()
        fix_edit.setReadOnly(True)
        fix_edit.setPlainText(explanation.get("fix", ""))
        fix_edit.setMaximumHeight(110)
        fix_edit.setStyleSheet(
            f"background: {WINDOW_BG}; color: {SUCCESS}; "
            f"border: 2px inset {SHADOW}; font-family: {FONT_MONO}; "
            f"font-size: 11px;"
        )
        layout.addWidget(fix_edit)

        # Coursera link
        course = get_course_link(finding.get("type", ""), desc_text)
        if course:
            course_label = QLabel(
                f'<a href="{course["url"]}" style="color: {TITLE_DARK};">'
                f'{_t("learn_more")}: {course["title"]}</a>'
            )
            course_label.setOpenExternalLinks(True)
            course_label.setStyleSheet(
                f"padding: 4px; font-family: {FONT_UI};"
            )
            layout.addWidget(course_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_skip = QPushButton("Skip")
        btn_skip.setToolTip("Dismiss until next session")
        btn_skip.setStyleSheet(BUTTON_STYLE)
        btn_skip.clicked.connect(lambda: self.done(self.DISMISSED))
        btn_row.addWidget(btn_skip)

        btn_close_all = QPushButton("Close All")
        btn_close_all.setStyleSheet(BUTTON_STYLE)
        btn_close_all.clicked.connect(lambda: self.done(self.DISMISSED_ALL))
        btn_row.addWidget(btn_close_all)

        btn = QPushButton(_t("understood"))
        btn.setStyleSheet(DANGER_BUTTON_STYLE)
        btn.clicked.connect(self.accept)
        btn_row.addWidget(btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    @classmethod
    def show_if_new(cls, finding: dict, parent=None) -> None:
        if cls._dismiss_all:
            return
        desc = finding.get("description", "")
        if desc in cls._shown_findings:
            return
        cls._shown_findings.add(desc)
        dlg = cls(finding, parent)
        result = dlg.exec_()
        if result == cls.DISMISSED:
            pass  # already in _shown_findings
        elif result == cls.DISMISSED_ALL:
            cls._dismiss_all = True


class SecurityScanThread(QThread):
    scan_done = pyqtSignal(list)

    def __init__(self, scanner_fn):
        super().__init__()
        self._scanner_fn = scanner_fn

    def run(self):
        try:
            findings = self._scanner_fn()
            self.scan_done.emit(findings)
        except Exception:
            self.scan_done.emit([])


class SecurityPage(QWidget):
    scan_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        counter_layout = QHBoxLayout()
        self.counters = {}
        for sev in ["critical", "high", "medium", "low"]:
            fg, bg = SEVERITY_COLORS[sev]
            label = QLabel(f" {sev.upper()}: 0 ")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {fg}; "
                f"background: {bg}; border: 2px outset #dfdfdf; "
                f"padding: 4px 12px; font-family: {FONT_UI};"
            )
            self.counters[sev] = label
            counter_layout.addWidget(label)
        layout.addLayout(counter_layout)

        splitter = QSplitter(Qt.Vertical)

        self.table = CopyableTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [_t("sev"), _t("type"), _t("description"), _t("source")]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(CopyableTableWidget.SelectRows)
        self.table.setEditTriggers(CopyableTableWidget.NoEditTriggers)
        self.table.setStyleSheet(LIST_STYLE)
        self.table.currentCellChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        self.detail_panel = QGroupBox(_t("details"))
        self.detail_panel.setStyleSheet(GROUP_STYLE)
        detail_layout = QVBoxLayout()

        self.detail_what = QLabel("")
        self.detail_what.setWordWrap(True)
        self.detail_what.setStyleSheet(
            f"padding: 4px; font-family: {FONT_UI};"
        )

        self.detail_risk = QLabel("")
        self.detail_risk.setWordWrap(True)
        self.detail_risk.setStyleSheet(
            f"padding: 4px; color: {ERROR}; font-family: {FONT_UI};"
        )

        # Fix snippet — white field + monospace green text (Win95 DOS-ish).
        self.detail_fix = QTextEdit("")
        self.detail_fix.setReadOnly(True)
        self.detail_fix.setMaximumHeight(100)
        self.detail_fix.setStyleSheet(
            f"background: {WINDOW_BG}; color: {SUCCESS}; "
            f"border: 2px inset {SHADOW}; font-family: {FONT_MONO}; "
            f"font-size: 11px;"
        )

        self.detail_course = QLabel("")
        self.detail_course.setOpenExternalLinks(True)
        self.detail_course.setStyleSheet(
            f"padding: 4px; color: {TITLE_DARK}; font-family: {FONT_UI};"
        )
        self.detail_course.hide()

        detail_layout.addWidget(QLabel(_t("what_is_this")))
        detail_layout.addWidget(self.detail_what)
        detail_layout.addWidget(QLabel(_t("risk")))
        detail_layout.addWidget(self.detail_risk)
        detail_layout.addWidget(QLabel(_t("how_to_fix")))
        detail_layout.addWidget(self.detail_fix)
        detail_layout.addWidget(QLabel(_t("learn_more")))
        detail_layout.addWidget(self.detail_course)
        self.detail_panel.setLayout(detail_layout)
        self.detail_panel.hide()
        splitter.addWidget(self.detail_panel)

        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        self.btn_scan = QPushButton(_t("scan_now"))
        self.btn_scan.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.btn_scan.clicked.connect(self.scan_requested.emit)
        btn_layout.addWidget(self.btn_scan)
        self.last_scan_label = QLabel(_t("last_scan_never"))
        self.last_scan_label.setStyleSheet(
            f"font-style: italic; color: {SHADOW}; font-family: {FONT_UI};"
        )
        btn_layout.addWidget(self.last_scan_label)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._findings: list[dict] = []

    def update_data(self, findings: list[dict]) -> None:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda f: order.get(f.get("severity", "low"), 4))
        self._findings = findings

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            counts[f.get("severity", "low")] = counts.get(f.get("severity", "low"), 0) + 1
        for sev, label in self.counters.items():
            label.setText(f" {sev.upper()}: {counts[sev]} ")

        self.table.setRowCount(len(findings))
        for i, f in enumerate(findings):
            sev = f.get("severity", "low")
            fg_hex, bg_hex = SEVERITY_COLORS.get(sev, ("#000", "#ccc"))

            sev_item = QTableWidgetItem(sev.upper())
            sev_item.setTextAlignment(Qt.AlignCenter)
            sev_item.setForeground(QColor(fg_hex))
            sev_item.setBackground(QColor(bg_hex))
            self.table.setItem(i, 0, sev_item)

            self.table.setItem(i, 1, QTableWidgetItem(f.get("type", "")))

            desc = get_human_description(f.get("type", ""), f.get("description", ""))
            self.table.setItem(i, 2, QTableWidgetItem(desc[:100]))

            self.table.setItem(i, 3, QTableWidgetItem(f.get("source", "")[:30]))

        from datetime import datetime
        self.last_scan_label.setText(_t("last_scan").format(datetime.now().strftime("%H:%M:%S")))

        if not getattr(self, "_suppress_popups", False):
            for f in findings:
                if f.get("severity") == "critical":
                    CriticalAlertDialog.show_if_new(f, self)

    def _on_row_selected(self, row, _col, _prev_row, _prev_col):
        if row < 0 or row >= len(self._findings):
            self.detail_panel.hide()
            return
        finding = self._findings[row]
        finding_type = finding.get("type", "")
        description = finding.get("description", "")
        explanation = get_explanation(finding_type, description)
        self.detail_what.setText(explanation["what"])
        self.detail_risk.setText(explanation["risk"])
        self.detail_fix.setPlainText(explanation["fix"])

        course = get_course_link(finding_type, description)
        if course:
            self.detail_course.setText(
                f'<a href="{course["url"]}" style="color:#5599ff;">'
                f'{_t("learn_more")}: {course["title"]}</a>'
            )
            self.detail_course.show()
        else:
            self.detail_course.hide()

        self.detail_panel.show()

    def set_scanning(self, scanning: bool) -> None:
        self.btn_scan.setEnabled(not scanning)
        self.btn_scan.setText(_t("scanning") if scanning else "Scan Now")

    def critical_count(self) -> int:
        return sum(1 for f in self._findings if f.get("severity") in ("critical", "high"))
