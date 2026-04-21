"""Win95 stylesheet for the main window and child widgets."""

WIN95_STYLE = """
QMainWindow, QWidget { background-color: #c0c0c0; font-family: "MS Sans Serif", "Liberation Sans", Arial, sans-serif; font-size: 12px; }
QPushButton { background: #c0c0c0; border: 2px outset #dfdfdf; padding: 4px 12px; font-weight: bold; }
QPushButton:pressed { border: 2px inset #808080; }
QProgressBar { border: 2px inset #808080; background: white; text-align: center; height: 20px; }
QProgressBar::chunk { background: #000080; }
QGroupBox { border: 2px groove #808080; margin-top: 12px; padding-top: 16px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QTableWidget { background: white; border: 2px inset #808080; gridline-color: #808080; }
QHeaderView::section { background: #c0c0c0; border: 1px outset #dfdfdf; padding: 2px; font-weight: bold; }
QComboBox { background: white; border: 2px inset #808080; padding: 2px; color: #000000; }
QComboBox QAbstractItemView { background: white; color: #000000; selection-background-color: #000080; selection-color: white; }
QComboBox QAbstractItemView::item:hover { background: #000080; color: white; }
QLabel { color: #000000; }
QMenuBar { background: #c0c0c0; border-bottom: 1px solid #808080; }
QMenuBar::item:selected { background: #000080; color: white; }
QMenu { background: #c0c0c0; border: 2px outset #dfdfdf; }
QMenu::item:selected { background: #000080; color: white; }
QStatusBar { background: #c0c0c0; border-top: 2px groove #808080; }
QCheckBox { spacing: 6px; }
QSpinBox { background: white; border: 2px inset #808080; padding: 2px; }
"""
