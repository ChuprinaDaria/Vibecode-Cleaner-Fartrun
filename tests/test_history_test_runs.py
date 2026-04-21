"""Tests for test_runs table in HistoryDB."""
from core.history import HistoryDB


def _sample_run(project_dir="/tmp/proj", started=1000.0, **overrides):
    base = dict(
        project_dir=project_dir,
        framework="pytest",
        command=["pytest", "-x"],
        started_at=started,
        finished_at=started + 5.0,
        duration_s=5.0,
        exit_code=0,
        timed_out=False,
        passed=10, failed=0, errors=0, skipped=1,
        output_tail="10 passed in 5s",
    )
    base.update(overrides)
    return base


def test_save_and_get_last_test_run():
    db = HistoryDB(":memory:")
    db.init()
    row_id = db.save_test_run(_sample_run())
    assert row_id > 0
    last = db.get_last_test_run("/tmp/proj")
    assert last["framework"] == "pytest"
    assert last["passed"] == 10
    assert last["command"] == ["pytest", "-x"]
    db.close()


def test_get_test_runs_returns_newest_first():
    db = HistoryDB(":memory:")
    db.init()
    db.save_test_run(_sample_run(started=1000.0))
    db.save_test_run(_sample_run(started=2000.0, exit_code=1, failed=2, passed=8))
    runs = db.get_test_runs("/tmp/proj")
    assert len(runs) == 2
    assert runs[0]["started_at"] == 2000.0
    assert runs[0]["failed"] == 2
    db.close()


def test_get_test_runs_filters_by_project():
    db = HistoryDB(":memory:")
    db.init()
    db.save_test_run(_sample_run(project_dir="/a"))
    db.save_test_run(_sample_run(project_dir="/b"))
    assert len(db.get_test_runs("/a")) == 1
    assert len(db.get_test_runs("/b")) == 1
    db.close()


def test_save_test_run_prunes_to_history_limit():
    db = HistoryDB(":memory:")
    db.init()
    for i in range(105):
        db.save_test_run(_sample_run(started=float(i)))
    runs = db.get_test_runs("/tmp/proj", limit=200)
    assert len(runs) == 100  # default history_limit
    # oldest 5 pruned: started_at 0..4 gone
    assert min(r["started_at"] for r in runs) == 5.0
    db.close()


def test_get_last_test_run_none_when_empty():
    db = HistoryDB(":memory:")
    db.init()
    assert db.get_last_test_run("/nope") is None
    db.close()
