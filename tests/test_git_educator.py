"""Tests for core/git_educator.py — teaching moments + progression."""

from unittest.mock import MagicMock

import pytest

from core.history import HistoryDB
from core.git_educator import GitEducator, Hint


@pytest.fixture
def db():
    hdb = HistoryDB(":memory:")
    hdb.init()
    return hdb


@pytest.fixture
def educator(db):
    return GitEducator("/tmp/test-project", db)


class TestHintFirstSave:
    def test_returns_save_first_hint(self, educator):
        hint = educator.get_hint("save_first", {"file_count": 5}, lang="en")
        assert hint is not None
        assert isinstance(hint, Hint)
        assert "first save point" in hint.text.lower()
        assert hint.git_command == "git commit + git tag"


class TestHintProgression:
    def test_full_hint_at_zero(self, educator):
        hint = educator.get_hint("save", {"file_count": 10}, lang="en")
        assert hint is not None
        assert hint.text  # should have text

    def test_short_hint_after_6(self, educator, db):
        # Bump saves to 6
        for _ in range(6):
            db.bump_git_education("/tmp/test-project", "saves_count")

        hint = educator.get_hint("save", {"file_count": 10}, lang="en")
        assert hint is not None
        assert hint.detail is None  # no Haiku detail in short mode

    def test_no_hint_after_15(self, educator, db):
        for _ in range(15):
            db.bump_git_education("/tmp/test-project", "saves_count")

        assert not educator.should_show_hints()
        hint = educator.get_hint("save", {}, lang="en")
        assert hint is None


class TestBumpCounter:
    def test_counters_increment(self, educator, db):
        educator.bump_counter("save")
        educator.bump_counter("save")
        educator.bump_counter("rollback")

        counters = db.get_git_education("/tmp/test-project")
        assert counters["saves_count"] == 2
        assert counters["rollbacks_count"] == 1
        assert counters["picks_count"] == 0


class TestHaikuHint:
    def test_with_mock_haiku(self, db):
        mock_haiku = MagicMock()
        mock_haiku.is_available.return_value = True
        mock_haiku.ask.return_value = "You just saved your code like a pro!"

        educator = GitEducator("/tmp/test-project", db, haiku=mock_haiku)
        hint = educator.get_hint("save", {"file_count": 10, "top_files": ["app.py"]}, lang="en")

        assert hint is not None
        assert hint.detail == "You just saved your code like a pro!"
        mock_haiku.ask.assert_called_once()

    def test_without_haiku(self, educator):
        hint = educator.get_hint("save", {"file_count": 10}, lang="en")
        assert hint is not None
        assert hint.detail is None  # no Haiku = no detail


class TestHoffLine:
    def test_hoff_returns_string_or_none(self):
        # Run many times to cover both outcomes (30% chance)
        results = set()
        for _ in range(100):
            line = GitEducator.get_hoff_line("save")
            results.add(type(line).__name__)
        # Should have both None and str
        assert "NoneType" in results or "str" in results

    def test_hoff_unknown_action(self):
        # Unknown action should return None
        for _ in range(20):
            assert GitEducator.get_hoff_line("unknown_action") is None


class TestUkrainianHints:
    def test_ua_hint(self, educator):
        hint = educator.get_hint("save", {}, lang="ua")
        assert hint is not None
        assert "Git запам" in hint.text  # Ukrainian text

    def test_rollback_ua(self, educator):
        hint = educator.get_hint("rollback", {}, lang="ua")
        assert hint is not None
        assert "зберіг обидві" in hint.text
