"""QTableWidget with Ctrl+C support for copying selected rows."""

from PyQt5.QtWidgets import QTableWidget, QApplication
from PyQt5.QtCore import Qt


class CopyableTableWidget(QTableWidget):
    """QTableWidget that copies selected cells to clipboard on Ctrl+C.

    Wheel events are forwarded to the parent scroll area (if any) so that
    nested tables don't hijack page scrolling.
    """

    def wheelEvent(self, event):
        # Forward to parent QScrollArea instead of scrolling inside the table
        parent = self.parent()
        while parent is not None:
            from PyQt5.QtWidgets import QScrollArea
            if isinstance(parent, QScrollArea):
                QApplication.sendEvent(parent.verticalScrollBar(), event)
                return
            parent = parent.parent()
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            self._copy_selection()
        else:
            super().keyPressEvent(event)

    def _copy_selection(self):
        selection = self.selectedIndexes()
        if not selection:
            return

        rows = sorted(set(idx.row() for idx in selection))
        cols = sorted(set(idx.column() for idx in selection))

        lines = []
        for row in rows:
            cells = []
            for col in cols:
                item = self.item(row, col)
                cells.append(item.text() if item else "")
            lines.append("\t".join(cells))

        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
