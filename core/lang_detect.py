"""Dumb one-function language detector.

Vibe coders write in EN or UA. Anything else we don't care about here.
A single Cyrillic letter is enough to call it Ukrainian.
"""

from __future__ import annotations

import re

_CYR = re.compile(r"[\u0400-\u04FF]")


def detect_lang(text: str) -> str:
    """Return 'uk' if any Cyrillic letter is present, else 'en'."""
    if not text:
        return "en"
    return "uk" if _CYR.search(text) else "en"
