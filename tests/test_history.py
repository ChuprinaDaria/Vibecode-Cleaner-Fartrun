"""Tests for history DB."""

from core.history import HistoryDB


def test_save_and_load_daily_stats():
    db = HistoryDB(":memory:")
    db.init()
    db.save_daily_stats(
        date="2026-04-14", tokens=500000, cost=2.50,
        cache_efficiency=85.0, sessions=5, security_score=90,
    )
    stats = db.get_daily_stats(days=7)
    assert len(stats) == 1
    assert stats[0]["tokens"] == 500000
    assert stats[0]["cost"] == 2.50
    assert stats[0]["security_score"] == 90
    db.close()


def test_weekly_trend():
    db = HistoryDB(":memory:")
    db.init()
    for i in range(7):
        db.save_daily_stats(
            date=f"2026-04-{8+i:02d}",
            tokens=100000 * (i + 1),
            cost=0.50 * (i + 1),
            cache_efficiency=70 + i * 3,
            sessions=3 + i,
            security_score=80,
        )
    stats = db.get_daily_stats(days=7)
    assert len(stats) == 7
    # Should be ordered by date DESC
    assert stats[0]["date"] == "2026-04-14"
    assert stats[-1]["date"] == "2026-04-08"
    db.close()


def test_upsert():
    db = HistoryDB(":memory:")
    db.init()
    db.save_daily_stats("2026-04-14", 100, 1.0, 80.0, 3, 90)
    db.save_daily_stats("2026-04-14", 200, 2.0, 85.0, 5, 95)
    stats = db.get_daily_stats(days=7)
    assert len(stats) == 1
    assert stats[0]["tokens"] == 200  # updated
    db.close()
