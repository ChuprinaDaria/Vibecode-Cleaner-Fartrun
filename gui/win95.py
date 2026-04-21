"""Centralized Windows 95 styling tokens for the claude-monitor GUI.

Palette, font stacks, and Qt stylesheet fragments derived from the
``curiositech-windags-skills-windows-95-web-designer`` skill adapted to
PyQt5. Import constants from here instead of inlining styles in each
page — so a palette tweak propagates everywhere.

Key rules from the skill we respect:

* Gradient lives ONLY on title bars. Everywhere else uses solid fills.
* All shadows are hard pixel (1-2 px, no blur). Qt expresses these via
  ``border: 2px outset/inset`` and ``border-color`` tricks.
* Tahoma / MS Sans Serif 11 px is the UI font.
* Semantic palette slots (error/warning/success) stay saturated; we do
  NOT swap in pastel variants — Win95 did not.
"""
from __future__ import annotations


# --------------------------------------------------------------- palette

# Core Win95 system colours. Keep names aligned with the skill doc so a
# future designer can cross-reference CSS variables.
DESKTOP = "#008080"          # teal desktop (rarely used in Qt chrome)
GRAY = "#c0c0c0"             # window chrome, button base
BUTTON_FACE = "#dfdfdf"      # raised button surface
HIGHLIGHT = "#ffffff"        # top/left bevel
SHADOW = "#808080"           # bottom/right bevel
DARK_SHADOW = "#000000"      # outer shadow edge
WINDOW_BG = "#ffffff"        # content surface
TITLE_DARK = "#000080"       # active title gradient start / selection
TITLE_LIGHT = "#1084d0"      # active title gradient end
TITLE_INACTIVE_DARK = "#808080"
TITLE_INACTIVE_LIGHT = "#b5b5b5"
SELECTION = "#000080"
SELECTION_TEXT = "#ffffff"

# Semantic colours (not part of the core palette but used throughout the
# codebase for status signalling). Kept saturated on purpose.
ERROR = "#cc0000"
WARNING = "#cc8800"
SUCCESS = "#006600"
INFO = "#000080"

# Notification / attention fills (used for nags, yellow hint boxes).
NOTIFICATION_BG = "#ffffcc"   # "Tip of the Day" yellow
NOTIFICATION_BORDER = "#cccc00"
HINT_BG = "#fffff0"

# ------------------------------------------------------------ typography

FONT_UI = "'Tahoma', 'MS Sans Serif', 'Segoe UI', Arial, sans-serif"
FONT_MONO = "'Fixedsys Excelsior', 'Courier New', monospace"


# ------------------------------------------------------- title / headers

TITLE_BAR_GRADIENT = (
    f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    f"stop:0 {TITLE_DARK}, stop:1 {TITLE_LIGHT})"
)

# Win95 section header: gradient bar with white bold text, like a window
# title. Apply to a QLabel that sits at the top of a framed section.
SECTION_HEADER_STYLE = (
    f"QLabel {{ background: {TITLE_BAR_GRADIENT}; "
    f"color: white; font-weight: bold; font-size: 12px; "
    f"padding: 4px 8px; font-family: {FONT_UI}; }}"
)

# Page-level H1: navy text, bold, no background. Used at the top of each
# page next to the shared project selector.
PAGE_TITLE_STYLE = (
    f"color: {TITLE_DARK}; font-weight: bold; font-family: {FONT_UI};"
)


# ------------------------------------------------------------ containers

# GroupBox with grooved bevel and a title in the margin — the canonical
# Win95 container for a labelled cluster of widgets.
GROUP_STYLE = (
    f"QGroupBox {{ border: 2px groove {GRAY}; margin-top: 10px; "
    f"padding-top: 14px; font-weight: bold; font-family: {FONT_UI}; }}"
    f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; "
    f"padding: 0 4px; background: {GRAY}; }}"
)

# Raised frame — window-like content panel with outset bevel.
RAISED_FRAME_STYLE = (
    f"QFrame {{ border: 2px outset {GRAY}; background: {GRAY}; }}"
)

# Sunken frame — inset, for read-only data panels.
SUNKEN_FRAME_STYLE = (
    f"QFrame {{ border: 2px inset {SHADOW}; background: {WINDOW_BG}; }}"
)


# -------------------------------------------------------------- controls

# Primary button — navy fill, raised bevel. Pressed = inverted bevel.
PRIMARY_BUTTON_STYLE = (
    f"QPushButton {{ background: {TITLE_DARK}; color: white; "
    f"padding: 6px 14px; border: 2px outset #4040c0; "
    f"font-weight: bold; font-family: {FONT_UI}; }}"
    f"QPushButton:pressed {{ border: 2px inset {TITLE_DARK}; }}"
    f"QPushButton:disabled {{ background: {GRAY}; color: {SHADOW}; "
    f"border: 2px outset {GRAY}; }}"
)

# Default secondary button — gray chrome, raised bevel.
BUTTON_STYLE = (
    f"QPushButton {{ background: {BUTTON_FACE}; color: black; "
    f"padding: 4px 12px; border: 2px outset {BUTTON_FACE}; "
    f"font-family: {FONT_UI}; font-size: 11px; }}"
    f"QPushButton:pressed {{ border: 2px inset {SHADOW}; }}"
    f"QPushButton:disabled {{ color: {SHADOW}; border: 2px outset {GRAY}; }}"
)

# Success variant — green fill. Used for Save / Apply destructive-safe
# actions ("save point created", etc).
SUCCESS_BUTTON_STYLE = (
    f"QPushButton {{ background: {SUCCESS}; color: white; "
    f"padding: 4px 12px; border: 2px outset #00aa00; "
    f"font-weight: bold; font-family: {FONT_UI}; }}"
    f"QPushButton:pressed {{ border: 2px inset {SUCCESS}; }}"
)

# Destructive variant — red fill. Delete / Reset / Rollback-forever.
DANGER_BUTTON_STYLE = (
    f"QPushButton {{ background: {ERROR}; color: white; "
    f"padding: 4px 12px; border: 2px outset #ff3333; "
    f"font-weight: bold; font-family: {FONT_UI}; }}"
    f"QPushButton:pressed {{ border: 2px inset {ERROR}; }}"
)

# Inputs — sunken white field with inset bevel.
FIELD_STYLE = (
    f"QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, "
    f"QDoubleSpinBox {{ border: 2px inset {SHADOW}; "
    f"background: {WINDOW_BG}; padding: 3px 6px; "
    f"font-family: {FONT_UI}; font-size: 11px; }}"
    f"QLineEdit:focus, QTextEdit:focus {{ border: 2px inset {TITLE_DARK}; }}"
)

# Compact read-only display (status line, version history, ports line).
# White field with hard inset bevel.
COMPACT_STYLE = (
    f"padding: 4px 8px; background: {WINDOW_BG}; "
    f"border: 2px inset {SHADOW}; font-size: 11px; "
    f"font-family: {FONT_UI};"
)

# Numeric cell — fixed-width, right-aligned, monospace so digits stack.
NUM_STYLE = (
    f"background: {WINDOW_BG}; border: 2px inset {SHADOW}; "
    f"padding: 2px 6px; font-family: {FONT_MONO}; font-size: 11px;"
)

# Notification box — yellow "Tip of the Day" fill with dashed gold
# border. Use for nags, hints, "where you stopped" summaries.
NOTIFICATION_STYLE = (
    f"padding: 8px; background: {NOTIFICATION_BG}; color: black; "
    f"border: 2px inset {SHADOW}; font-family: {FONT_UI};"
)

# Hint strip — pale yellow band with a single gold border. Used for the
# short "why this page exists" copy under page titles.
HINT_STRIP_STYLE = (
    f"color: #333; font-size: 12px; padding: 10px 12px; "
    f"background: {HINT_BG}; border: 2px solid {NOTIFICATION_BORDER}; "
    f"font-family: {FONT_UI};"
)


# -------------------------------------------------------------- progress

# Win95 progress bar — hollow sunken trough with solid blue chunk.
# Matches the "Installing…" / "Copying files…" dialog progress bars.
PROGRESS_BAR_STYLE = (
    f"QProgressBar {{ border: 2px inset {SHADOW}; "
    f"background: {WINDOW_BG}; text-align: center; height: 22px; "
    f"color: white; font-family: {FONT_UI}; font-size: 11px; "
    f"font-weight: bold; }}"
    f"QProgressBar::chunk {{ background: {TITLE_DARK}; margin: 1px; }}"
)


# --------------------------------------------------------------- dividers

# Bevelled horizontal strip — thin 3D separator between sections.
# Use as a QFrame HLine replacement where a visible pixel groove is
# wanted without the full SECTION_HEADER chrome.
DIVIDER_STRIP_STYLE = (
    f"background: {GRAY}; border-top: 1px solid {HIGHLIGHT}; "
    f"border-bottom: 1px solid {SHADOW}; min-height: 2px; max-height: 2px;"
)


# ---------------------------------------------------------------- tabs

# Win95 tab widget — grey pane with raised tabs on top. Selected tab sits
# flush with the pane (no bottom border) so it looks like a foreground
# folder in a classic property sheet.
TAB_WIDGET_STYLE = (
    f"QTabWidget::pane {{ border: 2px outset {GRAY}; "
    f"background: {GRAY}; top: -1px; }}"
    f"QTabBar::tab {{ background: {BUTTON_FACE}; "
    f"border: 2px outset {GRAY}; border-bottom: none; "
    f"padding: 5px 14px; margin-right: 2px; "
    f"font-family: {FONT_UI}; font-size: 11px; color: black; }}"
    f"QTabBar::tab:selected {{ background: {GRAY}; "
    f"font-weight: bold; margin-bottom: -1px; padding-bottom: 6px; }}"
    f"QTabBar::tab:hover:!selected {{ background: #e8e8e8; }}"
)


# ---------------------------------------------------------------- lists

LIST_STYLE = (
    f"QListWidget, QTableWidget, QTreeWidget {{ "
    f"background: {WINDOW_BG}; border: 2px inset {SHADOW}; "
    f"font-family: {FONT_UI}; font-size: 11px; "
    f"alternate-background-color: #f0f0f0; }}"
    f"QListWidget::item:selected, QTableWidget::item:selected {{ "
    f"background: {SELECTION}; color: {SELECTION_TEXT}; }}"
    f"QHeaderView::section {{ background: {BUTTON_FACE}; "
    f"border: 2px outset {GRAY}; padding: 3px 6px; "
    f"font-weight: bold; font-family: {FONT_UI}; }}"
)

# -------------------------------------------------------------- scrollbars

SCROLLBAR_STYLE = (
    f"QScrollBar:vertical {{ background: {GRAY}; width: 16px; }}"
    f"QScrollBar::handle:vertical {{ background: {BUTTON_FACE}; "
    f"border: 2px outset {BUTTON_FACE}; min-height: 20px; }}"
    f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
    f"background: {BUTTON_FACE}; border: 2px outset {BUTTON_FACE}; "
    f"height: 16px; }}"
)


# ---------------------------------------------------------------- helpers

def severity_color(severity: str) -> str:
    """Map severity keyword to palette colour."""
    return {
        "critical": ERROR,
        "high": ERROR,
        "medium": WARNING,
        "low": SHADOW,
        "info": INFO,
        "success": SUCCESS,
    }.get(severity.lower(), SHADOW)


def traffic_light(pct: float) -> str:
    """Green/yellow/red for 0-100 metrics (usage, budget, cache hit)."""
    if pct < 33:
        return "#00cc00"
    if pct < 66:
        return "#ffcc00"
    return "#ff3333"
