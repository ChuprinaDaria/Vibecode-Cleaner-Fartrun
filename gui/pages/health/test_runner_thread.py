"""QThread wrapper around the sync TestRunner.

Emits `finished_run(TestRun)` once when the subprocess finishes (or is
killed by timeout). Owns no state beyond the runner + invocation args.
"""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from core.health.test_runner import TestRun, TestRunner


class TestRunnerThread(QThread):
    finished_run = pyqtSignal(object)  # emits TestRun

    def __init__(self, runner: TestRunner, project_dir: Path,
                 cmd: list[str], parent=None):
        super().__init__(parent)
        self._runner = runner
        self._project_dir = project_dir
        self._cmd = cmd

    def run(self) -> None:
        result = self._runner.run(self._project_dir, self._cmd)
        self.finished_run.emit(result)
