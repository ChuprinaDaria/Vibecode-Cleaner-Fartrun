"""Sync subprocess orchestration for the background test runner.

Pure stdlib; knows nothing about Qt or the database.
Plugin / GUI layers wrap this.
"""
from __future__ import annotations

import select
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TestRun:
    project_dir: str
    framework: str
    command: list[str]
    started_at: float
    finished_at: float | None
    duration_s: float
    exit_code: int | None
    timed_out: bool
    passed: int | None
    failed: int | None
    errors: int | None
    skipped: int | None
    output_tail: str


@dataclass
class ParseResult:
    passed: int | None
    failed: int | None
    errors: int | None
    skipped: int | None


class Parser(Protocol):
    def parse(self, output: str, exit_code: int) -> ParseResult: ...


class TestRunner:
    """Runs a test command in a subprocess, returns a `TestRun`.

    Sync. Knows nothing about Qt or DB. Call from a worker thread
    (e.g. `TestRunnerThread`) so it doesn't block the GUI.
    """

    _TAIL_LINES = 200
    _READ_INTERVAL_S = 0.1

    def __init__(self, parser: Parser, timeout_s: int = 600,
                 framework: str = "pytest"):
        self._parser = parser
        self._timeout = timeout_s
        self._framework = framework

    def run(self, project_dir: Path, cmd: list[str]) -> TestRun:
        started = time.time()
        deadline = time.monotonic() + self._timeout
        tail: deque[str] = deque(maxlen=self._TAIL_LINES)
        timed_out = False
        exit_code: int | None = None

        try:
            proc = subprocess.Popen(
                cmd, cwd=str(project_dir),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except FileNotFoundError as e:
            finished = time.time()
            return TestRun(
                project_dir=str(project_dir), framework=self._framework,
                command=list(cmd), started_at=started, finished_at=finished,
                duration_s=finished - started, exit_code=-1, timed_out=False,
                passed=None, failed=None, errors=None, skipped=None,
                output_tail=f"command not found: {e.filename or cmd[0]}",
            )
        except PermissionError as e:
            finished = time.time()
            return TestRun(
                project_dir=str(project_dir), framework=self._framework,
                command=list(cmd), started_at=started, finished_at=finished,
                duration_s=finished - started, exit_code=-1, timed_out=False,
                passed=None, failed=None, errors=None, skipped=None,
                output_tail=f"permission denied: {e.filename or cmd[0]}",
            )

        assert proc.stdout is not None
        while True:
            if time.monotonic() > deadline:
                proc.kill()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass  # zombie; record timeout anyway
                timed_out = True
                exit_code = None
                break
            ready, _, _ = select.select([proc.stdout], [], [], self._READ_INTERVAL_S)
            if ready:
                line = proc.stdout.readline()
                if line == "":  # EOF
                    proc.wait()
                    exit_code = proc.returncode
                    break
                tail.append(line.rstrip("\n"))
            elif proc.poll() is not None:
                # Drain remaining output.
                rest = proc.stdout.read() or ""
                for r in rest.splitlines():
                    tail.append(r)
                exit_code = proc.returncode
                break

        finished = time.time()
        output = "\n".join(tail)
        try:
            parsed = self._parser.parse(output, exit_code if exit_code is not None else -1)
        except Exception:
            parsed = ParseResult(passed=None, failed=None, errors=None, skipped=None)

        return TestRun(
            project_dir=str(project_dir), framework=self._framework,
            command=list(cmd), started_at=started, finished_at=finished,
            duration_s=finished - started,
            exit_code=exit_code, timed_out=timed_out,
            passed=parsed.passed, failed=parsed.failed,
            errors=parsed.errors, skipped=parsed.skipped,
            output_tail=output,
        )
