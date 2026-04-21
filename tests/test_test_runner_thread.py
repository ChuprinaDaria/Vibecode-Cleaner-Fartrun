"""Tests for TestRunnerThread (Qt wrapper around TestRunner)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtCore import QCoreApplication, QEventLoop, QTimer

from core.health.test_runner import TestRun
from gui.pages.health.test_runner_thread import TestRunnerThread


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


def test_thread_emits_finished_run_signal(qapp, tmp_path):
    fake_run = TestRun(
        project_dir=str(tmp_path), framework="pytest", command=["x"],
        started_at=1.0, finished_at=2.0, duration_s=1.0,
        exit_code=0, timed_out=False,
        passed=1, failed=0, errors=0, skipped=0, output_tail="ok",
    )
    fake_runner = MagicMock()
    fake_runner.run.return_value = fake_run

    thread = TestRunnerThread(fake_runner, tmp_path, ["x"])
    received = []
    thread.finished_run.connect(lambda r: received.append(r))

    loop = QEventLoop()
    thread.finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)  # safety
    thread.start()
    loop.exec_()

    assert len(received) == 1
    assert received[0].passed == 1
    fake_runner.run.assert_called_once_with(tmp_path, ["x"])
