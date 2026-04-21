"""Tests that two trigger calls during an in-flight run produce exactly
one TestRun row and one re-run, never queue more than one pending."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_coalescing_two_triggers_one_pending(qapp, tmp_path, monkeypatch):
    from gui.pages.health import page as page_mod
    from core.health.test_runner import TestRun

    page = page_mod.HealthPage()
    page._project_dir = str(tmp_path)
    page._config = {"tests": {"command": "", "timeout_s": 600, "history_limit": 100}}

    # Monkeypatch detect_framework so we don't read tmp_path's filesystem.
    monkeypatch.setattr(
        "gui.pages.health.page.detect_framework",
        lambda d: ("generic", ["true"]),
    )

    # Replace TestRunnerThread with a stub that doesn't actually start a thread.
    started_count = {"n": 0}
    pending_threads = []

    class StubThread:
        def __init__(self, runner, project_dir, cmd, parent=None):
            self._runner = runner
            self._project_dir = project_dir
            self._cmd = cmd
            self._slots = []
        def isRunning(self):
            return self in pending_threads
        def start(self):
            started_count["n"] += 1
            pending_threads.append(self)
        @property
        def finished_run(self):
            outer = self
            class _Sig:
                def connect(self_inner, slot):
                    outer._slots.append(slot)
            return _Sig()
        def fire_finished(self, run):
            pending_threads.remove(self)
            for slot in self._slots:
                slot(run)

    monkeypatch.setattr("gui.pages.health.page.TestRunnerThread", StubThread)
    # Patch HistoryDB.save_test_run to a no-op (we're not testing persistence).
    monkeypatch.setattr(
        "gui.pages.health.page.HistoryDB",
        lambda: MagicMock(save_test_run=lambda r: 1, get_last_test_run=lambda d: None,
                          get_test_runs=lambda d, limit=10: []),
    )

    page._on_run_tests()           # trigger #1 — starts run
    page._on_run_tests()           # trigger #2 — sets _needs_rerun
    page._on_run_tests()           # trigger #3 — _needs_rerun already True; no-op
    assert started_count["n"] == 1
    assert page._needs_rerun is True
    assert len(pending_threads) == 1

    # Simulate first thread finishing.
    fake_run = TestRun(
        project_dir=str(tmp_path), framework="generic", command=["true"],
        started_at=1.0, finished_at=2.0, duration_s=1.0,
        exit_code=0, timed_out=False,
        passed=None, failed=None, errors=None, skipped=None, output_tail="",
    )
    pending_threads[0].fire_finished(fake_run)

    # Coalesced re-run must have started.
    assert started_count["n"] == 2
    assert page._needs_rerun is False


def test_save_point_trigger_runs_when_enabled(qapp, tmp_path, monkeypatch):
    from gui.pages.health import page as page_mod

    page = page_mod.HealthPage()
    page._project_dir = str(tmp_path)
    page._config = {"tests": {"trigger_on_save_point": True, "command": "", "timeout_s": 600}}
    started = {"n": 0}
    monkeypatch.setattr(page, "_on_run_tests", lambda: started.update(n=started["n"] + 1))
    page._on_save_point_created(str(tmp_path))
    assert started["n"] == 1


def test_save_point_trigger_silent_when_disabled(qapp, tmp_path, monkeypatch):
    from gui.pages.health import page as page_mod

    page = page_mod.HealthPage()
    page._project_dir = str(tmp_path)
    page._config = {"tests": {"trigger_on_save_point": False}}
    started = {"n": 0}
    monkeypatch.setattr(page, "_on_run_tests", lambda: started.update(n=started["n"] + 1))
    page._on_save_point_created(str(tmp_path))
    assert started["n"] == 0


def test_save_point_trigger_ignores_other_projects(qapp, tmp_path, monkeypatch):
    from gui.pages.health import page as page_mod

    page = page_mod.HealthPage()
    page._project_dir = str(tmp_path)
    page._config = {"tests": {"trigger_on_save_point": True}}
    started = {"n": 0}
    monkeypatch.setattr(page, "_on_run_tests", lambda: started.update(n=started["n"] + 1))
    page._on_save_point_created("/some/other/project")
    assert started["n"] == 0


def test_watch_debounce_collapses_burst(qapp, tmp_path, monkeypatch):
    from gui.pages.health import page as page_mod

    page = page_mod.HealthPage()
    page._project_dir = str(tmp_path)
    page._config = {"tests": {"watch": True, "debounce_ms": 50}}
    started = {"n": 0}
    monkeypatch.setattr(page, "_on_run_tests", lambda: started.update(n=started["n"] + 1))

    # Fire 5 events back-to-back; only one run after debounce window.
    for _ in range(5):
        page._on_watch_event()

    from PyQt5.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec_()

    assert started["n"] == 1
