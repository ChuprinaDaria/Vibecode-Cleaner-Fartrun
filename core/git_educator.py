"""Git teaching moments — explain what git did in human language.

Progression: 0-5 actions = full hints, 6-14 = short, 15+ = hidden.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from core.history import HistoryDB

log = logging.getLogger(__name__)


@dataclass
class Hint:
    text: str           # human explanation
    git_command: str     # real git command in parentheses
    detail: str | None = None  # Haiku-generated context or None


# Static hints: key -> (text_en, text_ua, git_command)
_HINTS = {
    "git_init": (
        "Git is a time machine for code. Just turned it on for this project.",
        "Git — це машина часу для коду. Щойно увімкнули її для цього проєкту.",
        "git init",
    ),
    "save": (
        "Git remembered your code exactly as it is now. You can always come back here.",
        "Git запам'ятав твій код саме таким, який він зараз. Завжди можеш сюди повернутись.",
        "git commit + git tag",
    ),
    "save_first": (
        "This is your first save point. Now you have a safety net. "
        "Before any risky change — save first, break things later.",
        "Це твоя перша точка збереження. Тепер у тебе є страховка. "
        "Перед будь-якою ризикованою зміною — спочатку зберігай, потім ламай.",
        "git commit + git tag",
    ),
    "gitignore": (
        "Told git to ignore junk files. They stay on disk but git won't track them.",
        "Сказали git ігнорувати сміттєві файли. Вони залишаються на диску, але git їх не відстежує.",
        ".gitignore",
    ),
    "rollback": (
        "Git kept both versions — the broken one in a backup branch, "
        "and your save point here. Switched you back. Nothing deleted.",
        "Git зберіг обидві версії — зламану в резервній гілці, "
        "а твою точку збереження тут. Повернув тебе назад. Нічого не видалено.",
        "git branch + git reset",
    ),
    "pick": (
        "Git grabbed files from one version and put them into another. "
        "Like copy-paste between parallel universes.",
        "Git взяв файли з однієї версії і вставив в іншу. "
        "Як copy-paste між паралельними всесвітами.",
        "git checkout branch -- file",
    ),
    "branch": (
        "A branch is a separate copy of your code. "
        "Changes here don't touch the original. Like a draft document.",
        "Гілка — це окрема копія твого коду. "
        "Зміни тут не чіпають оригінал. Як чернетка документа.",
        "git branch",
    ),
    "hooks_nudge": (
        "You've been saving manually several times. There's a way to make checks automatic — "
        "it's called a git hook. Check the Hooks Guide in the Discover page.",
        "Ти вже зберігав вручну кілька разів. Є спосіб зробити перевірки автоматичними — "
        "це називається git hook. Подивись Гід по хуках на сторінці Знахідки.",
        "git hooks",
    ),
}

# Hasselhoff one-liners
HOFF_SAVE = [
    "The Hoff always saves before the stunt.",
    "Even Knight Rider had a backup plan.",
    "Don't hassle the save point.",
]
HOFF_ROLLBACK = [
    "The Hoff has been here before. Literally.",
    "Time travel. The Hoff invented it. Probably.",
    "Back to safety. The Hoff approves.",
]
HOFF_PICK = [
    "The Hoff doesn't leave good code behind.",
    "Selective rescue. Very Baywatch.",
    "Grab what works, leave the drama.",
]
HOFF_EMPTY = [
    "Even the Hoff takes a day off.",
    "Nothing to save. Suspicious.",
]


class GitEducator:
    def __init__(self, project_dir: str, db: HistoryDB, haiku=None):
        self._dir = project_dir
        self._db = db
        self._haiku = haiku  # HaikuClient or None

    def _get_counters(self) -> dict:
        return self._db.get_git_education(self._dir)

    def _total_actions(self) -> int:
        c = self._get_counters()
        return c["saves_count"] + c["rollbacks_count"] + c["picks_count"]

    def should_show_hints(self) -> bool:
        return self._total_actions() < 15

    def get_hint(self, action: str, context: dict | None = None, lang: str = "en") -> Hint | None:
        """Get teaching hint for an action.

        action: "save", "save_first", "rollback", "pick", "git_init", "gitignore", "branch"
        """
        total = self._total_actions()

        # 15+ actions: no hints (unless explicitly asked)
        if total >= 15:
            return None

        hint_data = _HINTS.get(action)
        if not hint_data:
            return None

        text_en, text_ua, git_cmd = hint_data
        text = text_ua if lang == "ua" else text_en

        # 6-14: short (text only, no detail)
        if total >= 6:
            return Hint(text=text, git_command=git_cmd)

        # 0-5: full (text + git_command + optional Haiku detail)
        detail = None
        if self._haiku and context:
            detail = self._ask_haiku(action, context, lang)

        return Hint(text=text, git_command=git_cmd, detail=detail)

    def _ask_haiku(self, action: str, context: dict, lang: str) -> str | None:
        if not self._haiku or not self._haiku.is_available():
            return None
        try:
            file_count = context.get("file_count", 0)
            top_files = context.get("top_files", [])
            top_str = ", ".join(top_files[:5]) if top_files else "various files"

            if lang == "ua":
                prompt = (
                    f"Поясни не-програмісту у 2 реченнях що щойно відбулось. "
                    f"Контекст: {action} на {file_count} файлах, включаючи {top_str}. "
                    f"Без жаргону."
                )
            else:
                prompt = (
                    f"Explain to a non-programmer in 2 sentences what just happened. "
                    f"Context: {action} on {file_count} files including {top_str}. "
                    f"No jargon."
                )
            return self._haiku.ask(prompt, max_tokens=150)
        except Exception as e:
            log.debug("Haiku hint error: %s", e)
            return None

    def get_hooks_nudge(self, lang: str = "en") -> Hint | None:
        """After 5th save, suggest hooks guide. One-time nudge."""
        c = self._get_counters()
        if c["saves_count"] == 5:
            return self.get_hint("hooks_nudge", lang=lang)
        return None

    def bump_counter(self, action: str) -> None:
        field_map = {
            "save": "saves_count",
            "save_first": "saves_count",
            "rollback": "rollbacks_count",
            "pick": "picks_count",
        }
        field = field_map.get(action)
        if field:
            self._db.bump_git_education(self._dir, field)

    @staticmethod
    def get_hoff_line(action: str) -> str | None:
        """30% chance of Hasselhoff one-liner."""
        if random.random() > 0.3:
            return None

        lines = {
            "save": HOFF_SAVE,
            "rollback": HOFF_ROLLBACK,
            "pick": HOFF_PICK,
            "empty": HOFF_EMPTY,
        }
        pool = lines.get(action, [])
        return random.choice(pool) if pool else None
