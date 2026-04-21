from . import en, ua

_LANGUAGES = {"en": en.STRINGS, "ua": ua.STRINGS}
_current = "en"


def set_language(lang: str) -> None:
    global _current
    if lang in _LANGUAGES:
        _current = lang


def get_language() -> str:
    return _current


def get_string(key: str) -> str:
    return _LANGUAGES.get(_current, _LANGUAGES["en"]).get(key, key)
