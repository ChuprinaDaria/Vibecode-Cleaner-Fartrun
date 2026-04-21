import glob
import logging
import os
import random
import subprocess
from pathlib import Path

from i18n import get_language

log = logging.getLogger(__name__)

PHRASES: dict[str, list[str]] = {
    "en": [
        "Don't Hassel the Hoff! You saved tokens, champ!",
        "Hasselhoff would be proud. Few tokens \u2014 big results!",
        "Looking for Freedom! And you found it \u2014 freedom from wasted tokens!",
        "Knight Rider says: efficiency is sexy.",
        "Baywatch mode: saving your budget like Hasselhoff saves the beach!",
        "Hasselhoff approved! Fewer tokens \u2014 more Baywatch time.",
        "The Berlin Wall fell. So did your token costs. HOFF!",
        "David Hasselhoff gives a standing ovation! Efficient coder!",
    ],
    "ua": [
        "Don't Hassel the Hoff! Ти зекономив токени, красунчик!",
        "Hasselhoff б пишався тобою. Мало токенів \u2014 багато результату!",
        "Looking for Freedom! І ти знайшов \u2014 свободу від зайвих токенів!",
        "Knight Rider каже: ефективність \u2014 це сексі.",
        "Baywatch mode: ти рятуєш свій бюджет як Hasselhoff рятує пляж!",
        "Hasselhoff approved! Менше токенів \u2014 більше часу на Baywatch.",
        "Берлінська стіна впала. Як і твої витрати на токени. HOFF!",
        "David Hasselhoff аплодує стоячи! Ефективний кодер!",
    ],
}


def _project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current, current.parent, current.parent.parent]:
        if (parent / "pyproject.toml").exists() or (parent / "sounds").is_dir():
            return parent
    return current.parent


def _hoff_sound_dir() -> Path:
    return _project_root() / "sounds" / "hasselhoff"


def _hoff_image_dir() -> Path:
    return _hoff_sound_dir()


def get_hoff_phrase() -> str:
    lang = get_language()
    return random.choice(PHRASES.get(lang, PHRASES["en"]))


def get_hoff_image() -> str | None:
    d = _hoff_image_dir()
    images = list(d.glob("hoff*.jpg")) + list(d.glob("hoff*.png"))
    if images:
        return str(random.choice(images))
    return None


def get_random_hoff_song() -> Path | None:
    """Pick a random Hasselhoff song from sounds/hasselhoff/."""
    d = _hoff_sound_dir()
    songs = [f for f in d.iterdir()
             if f.suffix.lower() == ".mp3" and f.stem.startswith("David")]
    if not songs:
        # Fallback: any mp3 in the dir
        songs = [f for f in d.iterdir() if f.suffix.lower() == ".mp3"]
    return random.choice(songs) if songs else None


# ── Hasselhoff player with stop support ──────────────────────────

_current_process: subprocess.Popen | None = None


def play_hoff() -> Path | None:
    """Play a random Hasselhoff song. Returns the path played, or None."""
    global _current_process
    stop_hoff()  # stop previous if still playing

    song = get_random_hoff_song()
    if not song:
        log.warning("No Hasselhoff songs in %s", _hoff_sound_dir())
        return None

    from core.platform import get_platform
    _current_process = get_platform().play_sound(song)
    return song


def stop_hoff() -> None:
    """Stop currently playing Hasselhoff song."""
    global _current_process
    if _current_process is not None:
        try:
            _current_process.terminate()
            _current_process.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                _current_process.kill()
            except ProcessLookupError:
                pass
        _current_process = None


def is_hoff_playing() -> bool:
    """Check if a Hasselhoff song is currently playing."""
    global _current_process
    if _current_process is None:
        return False
    if _current_process.poll() is not None:
        _current_process = None
        return False
    return True
