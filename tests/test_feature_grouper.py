"""Tests for feature grouping — Haiku + fallback paths."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.feature_grouper import (
    FileChange, FeatureGroup,
    group_files_by_feature, _fallback_group, _haiku_group,
)


def _fc(path: str, adds: int = 10, dels: int = 0, status: str = "modified"):
    return FileChange(path=path, additions=adds, deletions=dels, status=status)


class TestFallback:
    def test_groups_by_top_level_dir(self):
        files = [
            _fc("src/auth/login.py"),
            _fc("src/auth/session.py"),
            _fc("src/dashboard/view.py"),
            _fc("README.md"),
        ]
        groups = _fallback_group(files)
        names = {g.name for g in groups}
        assert "Src" in names
        assert "Root Files" in names

    def test_empty_in_empty_out(self):
        assert _fallback_group([]) == []

    def test_dir_name_prettified(self):
        groups = _fallback_group([_fc("my_auth_module/a.py")])
        assert groups[0].name == "My Auth Module"


class TestHaikuGroup:
    def test_parses_json_response(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = (
            '[{"name": "Auth", "description": "login", '
            '"files": ["src/auth/login.py", "src/auth/session.py"]}, '
            '{"name": "Docs", "description": "readme", '
            '"files": ["README.md"]}]'
        )

        files = [
            _fc("src/auth/login.py"),
            _fc("src/auth/session.py"),
            _fc("README.md"),
        ]
        groups = _haiku_group(files, haiku)
        assert len(groups) == 2
        assert groups[0].name == "Auth"
        assert len(groups[0].files) == 2

    def test_strips_markdown_fences(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = (
            "```json\n"
            '[{"name": "Feature", "description": "", "files": ["a.py"]}]\n'
            "```"
        )
        groups = _haiku_group([_fc("a.py")], haiku)
        assert len(groups) == 1
        assert groups[0].name == "Feature"

    def test_invalid_json_returns_empty(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = "not json at all"
        groups = _haiku_group([_fc("a.py")], haiku)
        assert groups == []

    def test_ignores_unknown_files_from_haiku(self):
        """Haiku might hallucinate files we didn't give it — we drop those."""
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = (
            '[{"name": "Fake", "description": "", '
            '"files": ["fake_file_not_in_input.py"]}]'
        )
        groups = _haiku_group([_fc("real.py")], haiku)
        # Fake group is dropped (no real files), leftover "real.py" → Other
        assert any(g.name == "Other" for g in groups)

    def test_leftover_goes_to_other(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = (
            '[{"name": "Auth", "description": "", "files": ["auth.py"]}]'
        )
        files = [_fc("auth.py"), _fc("forgotten.py")]
        groups = _haiku_group(files, haiku)
        other = [g for g in groups if g.name == "Other"]
        assert len(other) == 1
        assert "forgotten.py" in other[0].files


class TestDispatch:
    def test_falls_back_when_no_haiku(self):
        groups = group_files_by_feature([_fc("src/a.py")], None)
        assert groups
        assert groups[0].name == "Src"

    def test_falls_back_when_haiku_unavailable(self):
        haiku = MagicMock()
        haiku.is_available.return_value = False
        groups = group_files_by_feature([_fc("src/a.py")], haiku)
        haiku.ask.assert_not_called()
        assert groups[0].name == "Src"

    def test_falls_back_when_haiku_returns_nothing(self):
        haiku = MagicMock()
        haiku.is_available.return_value = True
        haiku.ask.return_value = None
        groups = group_files_by_feature([_fc("src/a.py")], haiku)
        assert groups[0].name == "Src"
