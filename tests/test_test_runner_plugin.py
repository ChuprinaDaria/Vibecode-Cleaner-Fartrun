"""Tests for TestRunnerPlugin."""
import asyncio
import sys
from unittest.mock import patch

import pytest

# Bootstrap QApplication if PyQt5 is available, so plugin.render() can
# instantiate a QWidget. If Qt isn't installed, the render test is skipped.
try:
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication(sys.argv)
except ImportError:
    _app = None

from core.history import HistoryDB
from plugins.test_runner.plugin import TestRunnerPlugin


@pytest.fixture
def db():
    db = HistoryDB(":memory:")
    db.init()
    yield db
    db.close()


def test_plugin_metadata():
    plugin = TestRunnerPlugin(config={})
    assert plugin.name == "Tests"
    assert plugin.icon == "🧪"


def test_plugin_migrate_is_noop():
    """test_runs is owned by HistoryDB; plugin.migrate must not raise and
    must not touch the aiosqlite DB it gets passed."""
    plugin = TestRunnerPlugin(config={})
    asyncio.run(plugin.migrate(db=None))  # passing None is fine for a no-op


def test_plugin_collect_is_noop():
    plugin = TestRunnerPlugin(config={})
    asyncio.run(plugin.collect(db=None))


def test_plugin_render_returns_qwidget():
    if _app is None:
        pytest.skip("PyQt5 not available")
    plugin = TestRunnerPlugin(config={})
    w = plugin.render()
    # Don't import QWidget at module top — keeps the test runnable in
    # contexts where Qt isn't installed; here we just check the type name.
    assert type(w).__name__ in ("QWidget", "QFrame")


def test_get_alerts_returns_warning_when_last_run_failed(db):
    db.save_test_run({
        "project_dir": "/tmp/proj", "framework": "pytest",
        "command": ["pytest"], "started_at": 1.0, "finished_at": 2.0,
        "duration_s": 1.0, "exit_code": 1, "timed_out": False,
        "passed": 5, "failed": 2, "errors": 0, "skipped": 0,
        "output_tail": "2 failed",
    })
    plugin = TestRunnerPlugin(config={
        "plugins": {"test_runner": {"project_dir": "/tmp/proj"}}
    })
    with patch.object(plugin, "_history_db", return_value=db):
        alerts = asyncio.run(plugin.get_alerts(db=None))
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"
    assert "test" in alerts[0].title.lower()


def test_get_alerts_empty_when_last_run_passed(db):
    db.save_test_run({
        "project_dir": "/tmp/proj", "framework": "pytest",
        "command": ["pytest"], "started_at": 1.0, "finished_at": 2.0,
        "duration_s": 1.0, "exit_code": 0, "timed_out": False,
        "passed": 5, "failed": 0, "errors": 0, "skipped": 0,
        "output_tail": "all good",
    })
    plugin = TestRunnerPlugin(config={
        "plugins": {"test_runner": {"project_dir": "/tmp/proj"}}
    })
    with patch.object(plugin, "_history_db", return_value=db):
        alerts = asyncio.run(plugin.get_alerts(db=None))
    assert alerts == []


def test_get_alerts_empty_when_no_runs_yet(db):
    plugin = TestRunnerPlugin(config={
        "plugins": {"test_runner": {"project_dir": "/tmp/proj"}}
    })
    with patch.object(plugin, "_history_db", return_value=db):
        alerts = asyncio.run(plugin.get_alerts(db=None))
    assert alerts == []
