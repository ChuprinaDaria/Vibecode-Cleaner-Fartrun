"""Tests for changelog watcher."""

from unittest.mock import patch

from core.history import HistoryDB
from core.changelog_watcher import (
    get_claude_version, get_last_known_version, save_version,
    check_for_update, dismiss_version, is_dismissed,
)


def test_get_version_not_installed():
    with patch("shutil.which", return_value=None):
        assert get_claude_version() is None


def test_get_version_success():
    with patch("shutil.which", return_value="/usr/bin/claude"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "1.0.20\n"
            assert get_claude_version() == "1.0.20"


def test_get_version_prefixed():
    with patch("shutil.which", return_value="/usr/bin/claude"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "claude-code 1.0.20\n"
            assert get_claude_version() == "1.0.20"


def test_save_and_load_version():
    db = HistoryDB(":memory:")
    db.init()

    assert get_last_known_version(db) is None

    save_version(db, "1.0.19")
    assert get_last_known_version(db) == "1.0.19"

    save_version(db, "1.0.20")
    assert get_last_known_version(db) == "1.0.20"
    db.close()


def test_check_for_update_first_run():
    """First run — save version, no alert."""
    db = HistoryDB(":memory:")
    db.init()

    with patch("core.changelog_watcher.get_claude_version", return_value="1.0.20"):
        result = check_for_update(db)
    assert result is None
    assert get_last_known_version(db) == "1.0.20"
    db.close()


def test_check_for_update_no_change():
    """Same version — no alert."""
    db = HistoryDB(":memory:")
    db.init()
    save_version(db, "1.0.20")

    with patch("core.changelog_watcher.get_claude_version", return_value="1.0.20"):
        result = check_for_update(db)
    assert result is None
    db.close()


def test_check_for_update_version_changed():
    """Version changed — should alert."""
    db = HistoryDB(":memory:")
    db.init()
    save_version(db, "1.0.19")

    with patch("core.changelog_watcher.get_claude_version", return_value="1.0.20"):
        result = check_for_update(db)
    assert result is not None
    assert result["old_version"] == "1.0.19"
    assert result["new_version"] == "1.0.20"
    assert "changelog" in result["changelog_url"]
    db.close()


def test_dismissed_version_no_alert():
    """Dismissed version should not alert again."""
    db = HistoryDB(":memory:")
    db.init()
    save_version(db, "1.0.19")

    # First detection
    with patch("core.changelog_watcher.get_claude_version", return_value="1.0.20"):
        result = check_for_update(db)
    assert result is not None

    # Dismiss it
    dismiss_version(db, "1.0.20")
    assert is_dismissed(db, "1.0.20")

    # Check again — should not alert
    with patch("core.changelog_watcher.get_claude_version", return_value="1.0.20"):
        result = check_for_update(db)
    assert result is None
    db.close()


def test_claude_not_installed():
    """No claude binary — no alert, no crash."""
    db = HistoryDB(":memory:")
    db.init()

    with patch("core.changelog_watcher.get_claude_version", return_value=None):
        result = check_for_update(db)
    assert result is None
    db.close()
