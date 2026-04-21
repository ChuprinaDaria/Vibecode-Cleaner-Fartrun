"""Tests for core/prompt_builder.py — full pipeline including fallback."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from core.prompt_builder import (
    build_prompt, _fallback_keywords, _translate_to_keywords,
    _synthesize_prompt,
)
from core.code_searcher import CodeMatch
from core.stack_detector import DetectedLib


class TestFallbackKeywords:
    def test_picks_longer_words(self):
        kws = _fallback_keywords("fix the login button please")
        assert "login" in kws
        assert "button" in kws

    def test_lowercases(self):
        kws = _fallback_keywords("Fix Button")
        assert "button" in kws
        assert "fix" not in kws or "fix" == kws[0].lower()


class TestTranslateToKeywords:
    def test_uses_haiku_json(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = json.dumps({
            "keywords": ["button", "click"],
            "intent": "Fix the button click handler.",
        })
        kws, intent = _translate_to_keywords("кнопка не тиснеться", "uk", haiku)
        assert "button" in kws
        assert "Fix the button" in intent

    def test_strips_code_fences(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = (
            "```json\n"
            '{"keywords": ["auth"], "intent": "login"}\n'
            "```"
        )
        kws, intent = _translate_to_keywords("log in", "en", haiku)
        assert "auth" in kws

    def test_falls_back_on_bad_json(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = "not json"
        kws, intent = _translate_to_keywords("fix the login", "en", haiku)
        # Falls back to heuristic
        assert "login" in kws

    def test_falls_back_without_haiku(self):
        kws, intent = _translate_to_keywords("fix the login", "en", None)
        assert "login" in kws
        assert intent == "fix the login"


class TestSynthesize:
    def test_fallback_en(self):
        out, used_ai = _synthesize_prompt(
            user_text="fix login",
            intent="fix the login",
            language="en",
            matches=[CodeMatch(path="src/auth.py", line_number=10,
                                snippet="def login()", keyword="login")],
            stack=[DetectedLib(name="django", version="5.0", ecosystem="pypi")],
            context7_libs=["django"],
            frozen_paths=["config.py"],
            haiku_client=None,
        )
        assert used_ai is False
        assert "src/auth.py" in out
        assert "django" in out
        assert "config.py" in out
        assert "context7" in out.lower()

    def test_fallback_uk(self):
        out, used_ai = _synthesize_prompt(
            user_text="виправ логін",
            intent="fix the login",
            language="uk",
            matches=[],
            stack=[],
            context7_libs=[],
            frozen_paths=[],
            haiku_client=None,
        )
        assert "Задача" in out
        assert used_ai is False

    def test_uses_haiku_when_available(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = "FINAL PROMPT FROM HAIKU"
        out, used_ai = _synthesize_prompt(
            user_text="x", intent="x", language="en",
            matches=[], stack=[], context7_libs=[],
            frozen_paths=[], haiku_client=haiku,
        )
        assert used_ai is True
        assert "FINAL PROMPT FROM HAIKU" in out

    def test_falls_back_when_haiku_empty(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = ""
        out, used_ai = _synthesize_prompt(
            user_text="fix login", intent="fix", language="en",
            matches=[], stack=[], context7_libs=[],
            frozen_paths=[], haiku_client=haiku,
        )
        assert used_ai is False
        assert "Task:" in out


class TestBuildPromptFullPipeline:
    def test_end_to_end_without_haiku(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "login.py").write_text(
            "def login(user): pass\n"
        )
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = \"x\"\n"
            "dependencies = [\"django>=5.0\"]\n"
        )

        result = build_prompt(
            user_text="fix the login button",
            project_dir=str(tmp_path),
            haiku_client=None,
        )
        assert result.language == "en"
        assert result.used_ai is False
        assert "login" in result.final_prompt.lower()
        assert "django" in result.final_prompt.lower()

    def test_end_to_end_uk_lang(self, tmp_path):
        result = build_prompt(
            user_text="виправ логін",
            project_dir=str(tmp_path),
            haiku_client=None,
        )
        assert result.language == "uk"
        # UA fallback template header
        assert "Задача" in result.final_prompt
