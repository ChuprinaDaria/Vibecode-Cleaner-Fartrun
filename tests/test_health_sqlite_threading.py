"""Tests for HistoryDB thread safety (Task 18).

The GUI run log showed repeated warnings of the form:
  "SQLite objects created in a thread can only be used in that same
  thread. The object was created in thread id X and this is Y."

These happen because HistoryDB opened a connection in the main
thread, and QThread workers (StatusChecker, Haiku callbacks) called
execute() on it. Python's stdlib sqlite3 refuses cross-thread use by
default.

Fix: pass check_same_thread=False to sqlite3.connect and serialize
all execute/commit calls behind a single RLock.
"""
from __future__ import annotations

import threading

import pytest

from core.history import HistoryDB


def test_write_from_worker_thread(tmp_path):
    """A write issued from a non-main thread must succeed."""
    db = HistoryDB(str(tmp_path / "t.db"))
    db.init()

    errors: list[Exception] = []

    def worker():
        try:
            db.set_state("x", "hello")
        except Exception as e:  # pragma: no cover — test must fail noisily
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert not errors, f"write failed: {errors}"
    assert db.get_state("x") == "hello"


def test_concurrent_writes_from_many_threads(tmp_path):
    """10 workers × 20 rows must all land without data loss."""
    db = HistoryDB(str(tmp_path / "t.db"))
    db.init()

    N_THREADS = 10
    ROWS_PER = 20
    errors: list[Exception] = []

    def worker(thread_id: int):
        try:
            for i in range(ROWS_PER):
                db.save_activity(
                    project_dir=f"/tmp/proj{thread_id}",
                    timestamp=f"2026-04-16T00:00:{i:02d}",
                    entry_json="{}",
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"worker errors: {errors}"

    rows = db.execute("SELECT COUNT(*) FROM activity_log").fetchone()
    assert rows[0] == N_THREADS * ROWS_PER, f"expected {N_THREADS * ROWS_PER}, got {rows[0]}"


def test_read_from_worker_after_main_write(tmp_path):
    """Main writes, worker reads — both on the same connection."""
    db = HistoryDB(str(tmp_path / "t.db"))
    db.init()
    db.set_state("k", "v")

    result: list[str | None] = []

    def reader():
        result.append(db.get_state("k"))

    t = threading.Thread(target=reader)
    t.start()
    t.join()

    assert result == ["v"]


def test_repeated_writes_dont_trigger_threading_error(tmp_path, caplog):
    """Regression: status_checker-style write loop from a worker thread
    must not emit the SQLite threading warning to the log."""
    import logging

    db = HistoryDB(str(tmp_path / "t.db"))
    db.init()

    def worker():
        for _ in range(50):
            db.execute(
                "INSERT OR REPLACE INTO app_state(key, value) VALUES(?, ?)",
                ("x", "y"),
            )
            db.commit()

    with caplog.at_level(logging.WARNING):
        t = threading.Thread(target=worker)
        t.start()
        t.join()

    errors = [r for r in caplog.records if "thread" in r.getMessage().lower()]
    assert not errors, f"threading warnings: {[r.getMessage() for r in errors]}"
