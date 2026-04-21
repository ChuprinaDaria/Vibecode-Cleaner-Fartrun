"""Hasselhoff Vibecode Wizard — install Git, IDEs & Claude Code with MAXIMUM HOFF."""

import json
import os
import platform
import random
import shutil
import subprocess
from pathlib import Path

from PyQt5.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QMessageBox, QInputDialog,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QFont, QDesktopServices

from gui.win95 import (
    BUTTON_STYLE, DANGER_BUTTON_STYLE, ERROR, FONT_UI, GRAY, NOTIFICATION_BG,
    NOTIFICATION_BORDER, PRIMARY_BUTTON_STYLE, PROGRESS_BAR_STYLE,
    SECTION_HEADER_STYLE, SHADOW, SUCCESS_BUTTON_STYLE, TITLE_BAR_GRADIENT,
    TITLE_DARK, WINDOW_BG,
)
from i18n import get_string, get_language

# ─── HASSELHOFF ASCII ART ────────────────────────────────────────────────
HOFF_ASCII = r"""
    ╔══════════════════════════════════════════════════╗
    ║    ██╗  ██╗ ██████╗ ███████╗███████╗██╗██╗██╗   ║
    ║    ██║  ██║██╔═══██╗██╔════╝██╔════╝██║██║██║   ║
    ║    ███████║██║   ██║█████╗  █████╗  ██║██║██║   ║
    ║    ██╔══██║██║   ██║██╔══╝  ██╔══╝  ╚═╝╚═╝╚═╝   ║
    ║    ██║  ██║╚██████╔╝██║     ██║     ██╗██╗██╗   ║
    ║    ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝     ╚═╝╚═╝╚═╝   ║
    ║         V I B E C O D E   W I Z A R D            ║
    ╚══════════════════════════════════════════════════╝
"""

# ─── PROGRESS PHRASES ────────────────────────────────────────────────────
SWIM_PHRASES = {
    "en": [
        "Hasselhoff is swimming to the server...",
        "Knight Rider downloading at 88 mph...",
        "Baywatch rescue in progress...",
        "The Hoff is flexing your internet connection...",
        "Running in slow motion across the beach of bytes...",
        "KITT is hacking the mainframe... just kidding, we're using apt...",
        "Hasselhoff once installed Linux with his bare hands...",
        "Don't Hassel the download! It's coming!",
        "The Berlin Wall of dependencies is falling...",
        "Singing 'Looking for Freedom' while compiling...",
        "Baywatch Mode: ENGAGED. Downloading like it's 1989!",
        "The Hoff doesn't wait for progress bars. Progress bars wait for the Hoff.",
    ],
    "ua": [
        "Хасселхофф пливе до сервера...",
        "Knight Rider завантажує на швидкості 88 миль/год...",
        "Байвотч-рятувальна операція в процесі...",
        "Хофф напружує твоє інтернет-з'єднання...",
        "Біжить в уповільненому русі по пляжу байтів...",
        "КІТТ хакає мейнфрейм... жартую, ми юзаємо apt...",
        "Хасселхофф одного разу встановив Linux голими руками...",
        "Don't Hassel the download! Вже летить!",
        "Берлінська стіна залежностей падає...",
        "Співає 'Looking for Freedom' під час компіляції...",
        "Режим Baywatch: АКТИВОВАНО. Завантажуємо ніби 1989-й!",
        "Хофф не чекає прогрес-барів. Прогрес-бари чекають Хоффа.",
    ],
}

ERROR_PHRASES = {
    "en": [
        "The Berlin Wall of errors! But Hasselhoff NEVER gives up!",
        "Even KITT crashed once. We'll fix this!",
        "Baywatch rescue FAILED?! That's never happened before!",
        "Hasselhoff is disappointed. But still loves you. Try again.",
        "The Hoff has seen worse. Remember that music video?",
        "*sad fart noise* — Something went wrong. The Hoff is investigating.",
    ],
    "ua": [
        "Берлінська стіна помилок! Але Хасселхофф НІКОЛИ не здається!",
        "Навіть КІТТ одного разу крашнувся. Ми це полагодимо!",
        "Байвотч-рятунок ПРОВАЛИВСЯ?! Таке ніколи не траплялось!",
        "Хасселхофф розчарований. Але все ще любить тебе. Спробуй ще.",
        "Хофф бачив гірше. Пам'ятаєш той кліп?",
        "*сумний пердіж* — Щось пішло не так. Хофф розслідує.",
    ],
}

SUCCESS_PHRASES = {
    "en": [
        "HASSELHOFF APPROVES! Installation complete!",
        "Don't Hassel the Hoff! You did it, champ!",
        "Baywatch mission COMPLETE! Another life saved!",
        "Knight Rider says: EXCELLENT installation!",
        "The Hoff gives you a standing ovation! *victory fart*",
        "Looking for Freedom! And you FOUND it — freedom to code!",
        "The Berlin Wall fell. So did your installation barriers. HOFF!",
    ],
    "ua": [
        "ХАССЕЛХОФФ СХВАЛЮЄ! Встановлення завершено!",
        "Don't Hassel the Hoff! Ти зробив це, красунчик!",
        "Місія Baywatch ВИКОНАНА! Ще одне життя врятовано!",
        "Knight Rider каже: ВІДМІННЕ встановлення!",
        "Хофф аплодує стоячи! *пердіж перемоги*",
        "Looking for Freedom! І ти ЗНАЙШОВ — свободу кодити!",
        "Берлінська стіна впала. Як і твої бар'єри встановлення. HOFF!",
    ],
}

ALL_INSTALLED_PHRASES = {
    "en": [
        "ALL TOOLS INSTALLED! You're a Hasselhoff-certified vibecoder!",
        "FULL BAYWATCH MODE! Every tool is ready. Time to code like the Hoff!",
        "Knight Rider's cockpit is fully operational! Start vibecoding!",
        "Hasselhoff has NOTHING left to install. You're PERFECT.",
        "The Hoff weeps tears of joy. Your setup is IMMACULATE.",
    ],
    "ua": [
        "ВСІ ІНСТРУМЕНТИ ВСТАНОВЛЕНІ! Ти Хасселхофф-сертифікований вайбкодер!",
        "ПОВНИЙ РЕЖИМ BAYWATCH! Все готово. Час кодити як Хофф!",
        "Кокпіт Knight Rider повністю операційний! Починай вайбкодити!",
        "Хасселхоффу НІЧОГО більше ставити. Ти ІДЕАЛЬНИЙ.",
        "Хофф плаче сльозами радості. Твій сетап БЕЗДОГАННИЙ.",
    ],
}

# ─── Status labels ────────────────────────────────────────────────────────
STATUS_INSTALLED = {
    "en": "INSTALLED — Hasselhoff approves!",
    "ua": "ВСТАНОВЛЕНО — Хасселхофф схвалює!",
}
STATUS_MISSING = {
    "en": "MISSING — Even the Hoff is disappointed",
    "ua": "ВІДСУТНІЙ — Навіть Хофф розчарований",
}
STATUS_INSTALLING = {
    "en": "INSTALLING — Baywatch rescue in progress...",
    "ua": "ВСТАНОВЛЕННЯ — Байвотч-рятунок в процесі...",
}
STATUS_DOWNLOADING = {
    "en": "DOWNLOADING — Knight Rider at full speed...",
    "ua": "ЗАВАНТАЖЕННЯ — Knight Rider на повній швидкості...",
}


def _get_os():
    s = platform.system().lower()
    if s == "linux":
        return "linux"
    elif s == "darwin":
        return "mac"
    elif s == "windows":
        return "windows"
    return "unknown"


def _detect_pkg_manager():
    """Detect Linux package manager."""
    for cmd, pm in [("apt", "apt"), ("dnf", "dnf"), ("pacman", "pacman")]:
        if shutil.which(cmd):
            return pm
    return None


def _check_installed(tool: dict) -> bool:
    """Check if a tool is installed by running its check_command."""
    cmd = tool.get("check_command")
    if not cmd:
        return False
    try:
        result = subprocess.run(
            cmd.split(), capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    # Fallback: check known paths
    for p in tool.get("check_paths", []):
        if os.path.exists(p):
            return True
    return False


def _check_dependency(tool: dict) -> bool:
    """Check if required dependency (e.g. node for claude_code) exists."""
    req = tool.get("requires_check")
    if not req:
        return True
    try:
        result = subprocess.run(req.split(), capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class InstallThread(QThread):
    """Background thread for installing a tool."""
    progress = pyqtSignal(str)  # status message
    finished_ok = pyqtSignal(str)  # tool_key
    finished_err = pyqtSignal(str, str)  # tool_key, error

    def __init__(self, tool_key: str, tool_data: dict, parent=None):
        super().__init__(parent)
        self.tool_key = tool_key
        self.tool_data = tool_data

    def run(self):
        os_type = _get_os()
        try:
            if os_type == "linux":
                self._install_linux()
            else:
                self._download_for_os(os_type)
        except Exception as e:
            self.finished_err.emit(self.tool_key, str(e))

    def _install_linux(self):
        install = self.tool_data.get("install", {})

        # Try "all" first (e.g. npm install -g ...)
        if "all" in install:
            self.progress.emit("Running: " + install["all"])
            result = subprocess.run(
                install["all"].split(),
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                self.finished_ok.emit(self.tool_key)
            else:
                self.finished_err.emit(self.tool_key, result.stderr or "Install failed")
            return

        # Try snap first
        if "linux_snap" in install:
            snap_cmd = install["linux_snap"]
            self.progress.emit(f"Running: sudo {snap_cmd}")
            result = self._run_privileged(snap_cmd)
            if result == 0:
                self.finished_ok.emit(self.tool_key)
                return

        # Try linux command (e.g. "snap install cursor")
        if "linux" in install:
            cmd = install["linux"]
            self.progress.emit(f"Running: sudo {cmd}")
            result = self._run_privileged(cmd)
            if result == 0:
                self.finished_ok.emit(self.tool_key)
                return

        # Try package manager
        pm = _detect_pkg_manager()
        pkg_key = f"linux_{pm}" if pm else None
        if pkg_key and pkg_key in install:
            pkg = install[pkg_key]
            if pm == "apt":
                cmd = f"apt install -y {pkg}"
            elif pm == "dnf":
                cmd = f"dnf install -y {pkg}"
            elif pm == "pacman":
                cmd = f"pacman -S --noconfirm {pkg}"
            else:
                self.finished_err.emit(self.tool_key, f"Unknown package manager: {pm}")
                return

            self.progress.emit(f"Running: sudo {cmd}")
            result = self._run_privileged(cmd)
            if result == 0:
                self.finished_ok.emit(self.tool_key)
            else:
                self.finished_err.emit(self.tool_key, f"Package install failed (exit {result})")
            return

        # Fallback — open download page
        self._download_for_os("linux")

    def _run_privileged(self, cmd: str) -> int:
        """Run command with pkexec (graphical sudo) or fallback to xterm."""
        if shutil.which("pkexec"):
            full = ["pkexec"] + cmd.split()
        elif shutil.which("xterm"):
            full = ["xterm", "-e", f"sudo {cmd}; echo 'Press Enter...'; read"]
        else:
            full = ["sudo"] + cmd.split()

        try:
            result = subprocess.run(full, timeout=600)
            return result.returncode
        except subprocess.TimeoutExpired:
            return 1
        except Exception:
            return 1

    def _download_for_os(self, os_type: str):
        downloads = self.tool_data.get("download", {})
        url = downloads.get(os_type) or downloads.get("info")
        if url:
            self.progress.emit(f"Opening: {url}")
            QDesktopServices.openUrl(QUrl(url))
            self.finished_ok.emit(self.tool_key)
        else:
            self.finished_err.emit(self.tool_key, "No download URL available")


class ToolCard(QWidget):
    """Single tool card with status, install button, and Hoff phrase.

    Rendered as a Win95 property-sheet tile: outset bevel frame, a
    gradient title strip with the tool name, white body with an italic
    description, optional yellow "Tip of the Day" Hoff phrase, and a
    button strip along the bottom.
    """
    install_requested = pyqtSignal(str)  # tool_key

    def __init__(self, tool_key: str, tool_data: dict, parent=None):
        super().__init__(parent)
        self.tool_key = tool_key
        self.tool_data = tool_data

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        # --- Card frame (Win95 raised window) ---
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ border: 2px outset {GRAY}; background: {GRAY}; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # --- Title strip: icon + name (gradient bar, bold white) ---
        icon = tool_data.get("icon", "[?]")
        name = tool_data.get("name", tool_key)
        title_row = QFrame()
        title_row.setStyleSheet(
            f"QFrame {{ background: {TITLE_BAR_GRADIENT}; }}"
            f" QLabel {{ background: transparent; color: white; "
            f"font-weight: bold; font-family: {FONT_UI}; }}"
        )
        tr_layout = QHBoxLayout(title_row)
        tr_layout.setContentsMargins(6, 3, 6, 3)
        tr_layout.setSpacing(6)
        self.name_label = QLabel(f"{icon} {name}")
        self.name_label.setStyleSheet(
            f"background: transparent; color: white; font-weight: bold; "
            f"font-family: {FONT_UI}; font-size: 12px;"
        )
        tr_layout.addWidget(self.name_label)
        tr_layout.addStretch()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"background: transparent; color: white; font-weight: bold; "
            f"font-family: {FONT_UI}; font-size: 11px;"
        )
        tr_layout.addWidget(self.status_label)
        card_layout.addWidget(title_row)

        # --- Body (white sunken area with description + Hoff tip) ---
        body = QFrame()
        body.setStyleSheet(
            f"QFrame {{ background: {WINDOW_BG}; "
            f"border: 2px inset {SHADOW}; margin: 4px; }}"
        )
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(6)

        lang = get_language()
        desc = tool_data.get(f"description_{lang}", tool_data.get("description_en", ""))
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            f"color: black; font-style: italic; padding: 0; "
            f"font-family: {FONT_UI}; font-size: 11px; border: none;"
        )
        body_layout.addWidget(desc_label)

        phrases_key = f"hoff_phrases_{lang}"
        phrases = tool_data.get(phrases_key, tool_data.get("hoff_phrases_en", []))
        if phrases:
            phrase = random.choice(phrases)
            hoff_label = QLabel(f'"{phrase}"')
            hoff_label.setWordWrap(True)
            # Win95 "Tip of the Day" — pale yellow body, gold border,
            # navy text (same palette as the main app hint strip).
            hoff_label.setStyleSheet(
                f"color: {TITLE_DARK}; padding: 6px 8px; "
                f"background: {NOTIFICATION_BG}; "
                f"border: 1px solid {NOTIFICATION_BORDER}; "
                f"font-family: {FONT_UI}; font-size: 11px;"
            )
            body_layout.addWidget(hoff_label)

        card_layout.addWidget(body)

        # --- Button strip (right-aligned, dialog-style) ---
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(6, 0, 6, 6)
        btn_row.addStretch()
        self.install_btn = QPushButton("")
        self.install_btn.clicked.connect(
            lambda: self.install_requested.emit(self.tool_key)
        )
        btn_row.addWidget(self.install_btn)
        card_layout.addLayout(btn_row)

        outer.addWidget(card)

        self.refresh_status()

    def refresh_status(self):
        lang = get_language()
        installed = _check_installed(self.tool_data)

        if installed:
            self.status_label.setText(STATUS_INSTALLED.get(lang, STATUS_INSTALLED["en"]))
            self.install_btn.setText(
                "Installed — Hoff approves!" if lang == "en"
                else "Встановлено — Хофф схвалює!"
            )
            self.install_btn.setEnabled(False)
            self.install_btn.setStyleSheet(SUCCESS_BUTTON_STYLE)
        else:
            self.status_label.setText(STATUS_MISSING.get(lang, STATUS_MISSING["en"]))

            os_type = _get_os()
            if os_type == "linux":
                btn_text = "Install now!" if lang == "en" else "Встановити зараз!"
            else:
                btn_text = "Download" if lang == "en" else "Завантажити"

            self.install_btn.setText(btn_text)
            self.install_btn.setEnabled(True)
            self.install_btn.setStyleSheet(DANGER_BUTTON_STYLE)

    def set_installing(self):
        lang = get_language()
        self.status_label.setText(STATUS_INSTALLING.get(lang, STATUS_INSTALLING["en"]))
        self.install_btn.setEnabled(False)
        self.install_btn.setText(
            "Hasselhoff is swimming..." if lang == "en"
            else "Хасселхофф пливе..."
        )
        self.install_btn.setStyleSheet(BUTTON_STYLE)


class HasselhoffWizardPage(QWidget):
    """The ultimate vibecoding setup wizard powered by David Hasselhoff."""
    hoff_event = pyqtSignal(str)  # message for statusbar / hasselhoff trigger

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tools_data = {}
        self._cards: dict[str, ToolCard] = {}
        self._install_thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ─── HEADER: ASCII ART in a Win95 "About" window frame ───
        # Outer raised frame mimics the chrome of a dialog window;
        # inside sits a gradient title strip ("VIBECODE WIZARD") and
        # a sunken white body holding the ASCII art, like an icon
        # area inside an About box.
        header_frame = QFrame()
        header_frame.setStyleSheet(
            f"QFrame {{ border: 2px outset {GRAY}; background: {GRAY}; }}"
        )
        hf_layout = QVBoxLayout(header_frame)
        hf_layout.setContentsMargins(0, 0, 0, 0)
        hf_layout.setSpacing(0)

        self.title_strip = QLabel("")
        self.title_strip.setStyleSheet(SECTION_HEADER_STYLE)
        hf_layout.addWidget(self.title_strip)

        self.header = QLabel(HOFF_ASCII)
        self.header.setFont(QFont("Courier New", 8))
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet(
            f"background: {WINDOW_BG}; color: {TITLE_DARK}; padding: 8px; "
            f"border: 2px inset {SHADOW}; margin: 4px;"
        )
        self.header.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Easter egg: double-click for special Hoff moment
        self.header.mouseDoubleClickEvent = self._easter_egg
        hf_layout.addWidget(self.header)

        layout.addWidget(header_frame)

        # ─── SUBTITLE ─── Tahoma, navy, plain text on the page. ──
        self.subtitle = QLabel("")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {TITLE_DARK}; "
            f"padding: 8px 4px; font-family: {FONT_UI};"
        )
        layout.addWidget(self.subtitle)
        self._update_subtitle()

        # ─── INSTALL ALL BUTTON ─── Win95 primary (navy) / success green
        self.install_all_btn = QPushButton("")
        self.install_all_btn.clicked.connect(self._install_all_missing)
        layout.addWidget(self.install_all_btn)
        self._update_install_all_btn()

        # ─── PROGRESS BAR ─── classic Win95 chunky blue progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("")
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Progress phrase label — neutral gray italic like a status line.
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet(
            f"color: {SHADOW}; font-style: italic; padding: 4px; "
            f"font-family: {FONT_UI}; font-size: 11px;"
        )
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        # ─── TOOL CARDS (scrollable sunken list) ──────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 2px inset {SHADOW}; "
            f"background: {GRAY}; }}"
        )

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet(f"background: {GRAY};")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.cards_layout.setSpacing(4)
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)

        # ─── LOAD TOOLS ──────────────────────────────────────────
        self._load_tools_local()

        # ─── PHRASE ROTATION TIMER ────────────────────────────────
        self._phrase_timer = QTimer(self)
        self._phrase_timer.timeout.connect(self._rotate_phrase)

        # ─── INSTALL QUEUE ────────────────────────────────────────
        self._install_queue: list[str] = []

    def _update_subtitle(self):
        lang = get_language()
        if lang == "ua":
            self.title_strip.setText("Hasselhoff Vibecode Wizard")
            self.subtitle.setText(
                "Хасселхофф допоможе тобі стати вайбкодером! "
                "Перевір що встановлено і постав що потрібно."
            )
        else:
            self.title_strip.setText("Hasselhoff Vibecode Wizard")
            self.subtitle.setText(
                "Hasselhoff will help you become a vibecoder! "
                "Check what's installed and set up what's missing."
            )

    def _update_install_all_btn(self):
        lang = get_language()
        missing = [k for k, t in self._tools_data.items() if not _check_installed(t)]
        # Oversized variant of the Win95 token — primary (navy) when
        # there's work to do, success (green) when everything's ready.
        bigger = "padding: 12px 32px"
        if missing:
            n = len(missing)
            if lang == "ua":
                self.install_all_btn.setText(
                    f"BAYWATCH MODE — Встановити все ({n} відсутніх)"
                )
            else:
                self.install_all_btn.setText(
                    f"BAYWATCH MODE — Install ALL Missing ({n})"
                )
            self.install_all_btn.setStyleSheet(
                PRIMARY_BUTTON_STYLE.replace("padding: 6px 14px", bigger)
                + " QPushButton { font-size: 13px; }"
            )
            self.install_all_btn.setEnabled(True)
            self.install_all_btn.show()
        else:
            if lang == "ua":
                self.install_all_btn.setText(
                    "ВСЕ ВСТАНОВЛЕНО — Хофф пишається тобою!"
                )
            else:
                self.install_all_btn.setText(
                    "ALL INSTALLED — The Hoff is proud of you!"
                )
            self.install_all_btn.setStyleSheet(
                SUCCESS_BUTTON_STYLE.replace("padding: 4px 12px", bigger)
                + " QPushButton { font-size: 13px; }"
            )
            self.install_all_btn.setEnabled(False)

    def _load_tools_local(self):
        """Load tools.json from local repo."""
        tools_path = Path(__file__).resolve().parent.parent.parent / "tools.json"
        try:
            with open(tools_path) as f:
                data = json.load(f)
            self._tools_data = data.get("tools", {})
            self._build_cards()
        except (OSError, json.JSONDecodeError) as e:
            err = QLabel(f"Failed to load tools.json: {e}")
            err.setStyleSheet(
                f"color: {ERROR}; padding: 16px; font-weight: bold; "
                f"font-family: {FONT_UI};"
            )
            self.cards_layout.addWidget(err)

    def _build_cards(self):
        """Create ToolCard for each tool."""
        # Clear existing
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._cards.clear()

        for key, tool in self._tools_data.items():
            card = ToolCard(key, tool)
            card.install_requested.connect(self._on_install_requested)
            self.cards_layout.addWidget(card)
            self._cards[key] = card

        self._update_install_all_btn()

    def _on_install_requested(self, tool_key: str):
        """Handle install button click for a single tool."""
        tool = self._tools_data.get(tool_key)
        if not tool:
            return

        # Check dependency
        if not _check_dependency(tool):
            lang = get_language()
            hint_key = f"requires_install_hint_{lang}"
            hint = tool.get(hint_key, tool.get("requires_install_hint_en", ""))
            QMessageBox.warning(
                self, "Hasselhoff says: WAIT!",
                f"This tool requires {tool.get('requires', '???')}!\n\n{hint}\n\n"
                "Install the dependency first, then come back!\n"
                "Even Hasselhoff follows prerequisites!",
            )
            return

        # Git post-install: ask for config
        if tool_key == "git" and _check_installed(tool):
            self._git_config_wizard()
            return

        self._start_install(tool_key)

    def _start_install(self, tool_key: str):
        """Start installation in background thread."""
        if self._install_thread and self._install_thread.isRunning():
            self._install_queue.append(tool_key)
            return

        tool = self._tools_data[tool_key]
        card = self._cards.get(tool_key)
        if card:
            card.set_installing()

        # Show progress
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.progress_label.show()
        self._rotate_phrase()
        self._phrase_timer.start(3000)

        # Animate progress bar
        self._progress_value = 0
        self._progress_anim = QTimer(self)
        self._progress_anim.timeout.connect(self._animate_progress)
        self._progress_anim.start(200)

        # Start thread
        self._install_thread = InstallThread(tool_key, tool, self)
        self._install_thread.progress.connect(self._on_install_progress)
        self._install_thread.finished_ok.connect(self._on_install_ok)
        self._install_thread.finished_err.connect(self._on_install_error)
        self._install_thread.start()

    def _animate_progress(self):
        """Fake progress animation — because Hasselhoff never stands still."""
        if self._progress_value < 90:
            self._progress_value += random.randint(1, 5)
            self.progress_bar.setValue(self._progress_value)

    def _rotate_phrase(self):
        """Rotate swimming/progress phrases."""
        lang = get_language()
        phrases = SWIM_PHRASES.get(lang, SWIM_PHRASES["en"])
        self.progress_label.setText(random.choice(phrases))

    def _on_install_progress(self, msg: str):
        self.progress_label.setText(msg)

    def _on_install_ok(self, tool_key: str):
        """Installation succeeded!"""
        self._finish_progress()
        lang = get_language()

        # Refresh card
        card = self._cards.get(tool_key)
        if card:
            card.refresh_status()

        # Victory message
        phrase = random.choice(SUCCESS_PHRASES.get(lang, SUCCESS_PHRASES["en"]))
        tool_name = self._tools_data.get(tool_key, {}).get("name", tool_key)
        self.progress_label.setText(f"[OK]{tool_name}: {phrase}")
        self.progress_label.show()

        # Trigger Hasselhoff in main app
        self.hoff_event.emit(f"{tool_name} installed! {phrase}")

        self._update_install_all_btn()

        # Git post-install config
        if tool_key == "git":
            QTimer.singleShot(1000, self._git_config_wizard)

        # Check all installed
        self._check_all_installed()

        # Process queue
        QTimer.singleShot(2000, self._process_queue)

    def _on_install_error(self, tool_key: str, error: str):
        """Installation failed!"""
        self._finish_progress()
        lang = get_language()

        # Refresh card
        card = self._cards.get(tool_key)
        if card:
            card.refresh_status()

        # Error message
        phrase = random.choice(ERROR_PHRASES.get(lang, ERROR_PHRASES["en"]))
        tool_name = self._tools_data.get(tool_key, {}).get("name", tool_key)
        self.progress_label.setText(f"[ERR]{tool_name}: {phrase}")
        self.progress_label.setStyleSheet(
            f"color: {ERROR}; font-weight: bold; font-style: italic; "
            f"padding: 4px; font-family: {FONT_UI}; font-size: 11px;"
        )
        self.progress_label.show()

        # Show error detail
        QMessageBox.warning(
            self,
            f"Hasselhoff is sad about {tool_name}",
            f"{phrase}\n\nError: {error}\n\n"
            "Don't worry — even KITT had bad days.\n"
            "Try installing manually or check your internet connection.",
        )

        # Reset label style after delay — back to neutral Win95 gray.
        QTimer.singleShot(5000, lambda: self.progress_label.setStyleSheet(
            f"color: {SHADOW}; font-style: italic; padding: 4px; "
            f"font-family: {FONT_UI}; font-size: 11px;"
        ))

        # Process queue
        QTimer.singleShot(2000, self._process_queue)

    def _finish_progress(self):
        """Stop progress animation."""
        self.progress_bar.setValue(100)
        self._phrase_timer.stop()
        if hasattr(self, "_progress_anim"):
            self._progress_anim.stop()

    def _process_queue(self):
        """Install next tool in queue."""
        if self._install_queue:
            next_key = self._install_queue.pop(0)
            self._start_install(next_key)
        else:
            QTimer.singleShot(3000, self._hide_progress)

    def _hide_progress(self):
        if not (self._install_thread and self._install_thread.isRunning()):
            self.progress_bar.hide()
            self.progress_label.hide()

    def _install_all_missing(self):
        """BAYWATCH MODE: install everything that's missing."""
        missing = [k for k, t in self._tools_data.items() if not _check_installed(t)]
        if not missing:
            return

        lang = get_language()
        if lang == "ua":
            reply = QMessageBox.question(
                self, "РЕЖИМ BAYWATCH!",
                f"Хасселхофф готовий встановити {len(missing)} інструментів!\n\n"
                + "\n".join(f"  \u2022 {self._tools_data[k].get('name', k)}" for k in missing)
                + "\n\nЗапускаємо Baywatch Mode?",
                QMessageBox.Yes | QMessageBox.No,
            )
        else:
            reply = QMessageBox.question(
                self, "BAYWATCH MODE!",
                f"Hasselhoff is ready to install {len(missing)} tools!\n\n"
                + "\n".join(f"  \u2022 {self._tools_data[k].get('name', k)}" for k in missing)
                + "\n\nEngage Baywatch Mode?",
                QMessageBox.Yes | QMessageBox.No,
            )

        if reply == QMessageBox.Yes:
            # Queue all missing, respecting dependencies
            # Tools with dependencies go last
            no_deps = [k for k in missing if not self._tools_data[k].get("requires")]
            with_deps = [k for k in missing if self._tools_data[k].get("requires")]
            ordered = no_deps + with_deps

            if ordered:
                self._start_install(ordered[0])
                self._install_queue.extend(ordered[1:])

    def _check_all_installed(self):
        """Check if everything is installed — trigger MEGA HOFF."""
        missing = [k for k, t in self._tools_data.items() if not _check_installed(t)]
        if not missing and self._tools_data:
            lang = get_language()
            phrase = random.choice(ALL_INSTALLED_PHRASES.get(lang, ALL_INSTALLED_PHRASES["en"]))
            self.hoff_event.emit(phrase)

    def _git_config_wizard(self):
        """Post-install: configure git user.name and user.email."""
        lang = get_language()

        # Check if already configured
        try:
            name_result = subprocess.run(
                ["git", "config", "--global", "user.name"],
                capture_output=True, text=True, timeout=5,
            )
            email_result = subprocess.run(
                ["git", "config", "--global", "user.email"],
                capture_output=True, text=True, timeout=5,
            )
            if name_result.stdout.strip() and email_result.stdout.strip():
                return  # Already configured
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return

        title = ("Hasselhoff Git Config Wizard" if lang == "en"
                 else "Хасселхофф Git Config Визард")
        prompt_name = ("What's your name, vibecoder?\n\n"
                       "(Hasselhoff needs to know who to give credit to)"
                       if lang == "en" else
                       "Як тебе звати, вайбкодеру?\n\n"
                       "(Хасселхофф мусить знати кого хвалити)")

        name, ok = QInputDialog.getText(self, title, prompt_name)
        if not ok or not name:
            return

        prompt_email = ("And your email?\n\n"
                        "(For git commits, not Baywatch fan mail)"
                        if lang == "en" else
                        "І твій email?\n\n"
                        "(Для git комітів, не для фанатської пошти Baywatch)")

        email, ok = QInputDialog.getText(self, title, prompt_email)
        if not ok or not email:
            return

        try:
            subprocess.run(["git", "config", "--global", "user.name", name], timeout=5)
            subprocess.run(["git", "config", "--global", "user.email", email], timeout=5)

            msg = (f"Git configured!\n\n"
                   f"Name: {name}\nEmail: {email}\n\n"
                   f"Hasselhoff approves your identity!"
                   if lang == "en" else
                   f"Git налаштований!\n\n"
                   f"Ім'я: {name}\nEmail: {email}\n\n"
                   f"Хасселхофф схвалює твою ідентичність!")

            QMessageBox.information(self, title, msg)
            self.hoff_event.emit(f"Git configured for {name}! Knight Rider is ready!")
        except Exception as e:
            QMessageBox.warning(self, "Oops", f"Git config failed: {e}")

    def _easter_egg(self, event):
        """Double-click on header — MAXIMUM HOFF."""
        lang = get_language()

        hoff_wisdom = [
            "The Hoff once debugged a production server by staring at it.",
            "Hasselhoff doesn't use Stack Overflow. Stack Overflow uses Hasselhoff.",
            "KITT's AI was just Claude Code in a Pontiac Trans Am.",
            "The Berlin Wall fell because Hasselhoff's code had no walls.",
            "Hasselhoff's git log is just a list of victories.",
            "When Hasselhoff writes tests, they pass in ALL timelines.",
            "Hasselhoff doesn't refactor. He factors correctly the first time.",
            "npm install hasselhoff — installs confidence and beach muscles.",
        ]
        hoff_wisdom_ua = [
            "Хофф одного разу здебажив прод-сервер просто поглядом.",
            "Хасселхофф не юзає Stack Overflow. Stack Overflow юзає Хасселхоффа.",
            "ШІ КІТТа — це просто Claude Code в Понтіак Транс Ам.",
            "Берлінська стіна впала бо в коді Хасселхоффа немає стін.",
            "Git log Хасселхоффа — це просто список перемог.",
            "Коли Хасселхофф пише тести, вони проходять в УСІХ часових лініях.",
            "Хасселхофф не рефакторить. Він пише правильно з першого разу.",
            "npm install hasselhoff — встановлює впевненість і пляжні м'язи.",
        ]

        wisdom = hoff_wisdom_ua if lang == "ua" else hoff_wisdom
        phrase = random.choice(wisdom)

        QMessageBox.information(
            self,
            "*** HOFF WISDOM ***" if lang == "en" else "*** МУДРІСТЬ ХОФФА ***",
            f"\n{phrase}\n\n— David Hasselhoff, probably",
        )
        self.hoff_event.emit(phrase)

