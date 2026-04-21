"""Tests for StatusChecker — API status monitoring."""

import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from core.history import HistoryDB
from core.status_checker import StatusChecker, StatusResult, _ensure_status_table


def _make_status_json(indicator: str = "none", description: str = "All Systems Operational"):
    """Build a fake status.json response body."""
    return json.dumps({
        "page": {"id": "abc123"},
        "status": {
            "indicator": indicator,
            "description": description,
        },
    }).encode()


def _mock_urlopen(data: bytes, status: int = 200):
    """Create a mock response for urllib.request.urlopen."""
    resp = MagicMock()
    resp.read.return_value = data
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestParseStatus:
    def test_parse_status_ok(self):
        """indicator 'none' → api_indicator 'none', description passed through."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("none", "All Systems Operational")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result = checker.check_now()

        assert result.api_indicator == "none"
        assert result.api_description == "All Systems Operational"
        db.close()

    def test_parse_status_degraded(self):
        """indicator 'minor' → api_indicator 'minor'."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("minor", "Degraded Performance")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result = checker.check_now()

        assert result.api_indicator == "minor"
        assert result.api_description == "Degraded Performance"
        db.close()

    def test_parse_status_down(self):
        """indicator 'major' → api_indicator 'major'."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("major", "Major Outage")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result = checker.check_now()

        assert result.api_indicator == "major"
        db.close()

    def test_parse_status_critical(self):
        """indicator 'critical' → api_indicator 'critical'."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("critical", "Critical Outage")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result = checker.check_now()

        assert result.api_indicator == "critical"
        assert result.api_description == "Critical Outage"
        db.close()

    def test_timeout_returns_unknown(self):
        """Network error → api_indicator 'unknown'."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        with patch("core.status_checker.urlopen", side_effect=OSError("timeout")):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result = checker.check_now()

        assert result.api_indicator == "unknown"
        assert "timeout" in result.api_description.lower() or "error" in result.api_description.lower()
        db.close()

    def test_bad_json_returns_unknown(self):
        """Malformed JSON → api_indicator 'unknown'."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        bad_resp = _mock_urlopen(b"not json at all {{{")
        with patch("core.status_checker.urlopen", return_value=bad_resp):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result = checker.check_now()

        assert result.api_indicator == "unknown"
        db.close()

    def test_unexpected_indicator(self):
        """Unknown indicator string → api_indicator 'unknown'."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("banana", "Something weird")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result = checker.check_now()

        assert result.api_indicator == "unknown"
        db.close()


class TestSQLitePersistence:
    def test_save_and_load(self):
        """Round-trip: check_now saves, get_last_status loads."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("none", "All Systems Operational")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                original = checker.check_now()

        loaded = checker.get_last_status()
        assert loaded is not None
        assert loaded.api_indicator == original.api_indicator
        assert loaded.api_description == original.api_description
        assert loaded.claude_version == "1.0.20"
        db.close()

    def test_history_pruning(self):
        """Records older than 7 days are pruned on check_now."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)
        _ensure_status_table(db)

        # Insert an old record (8 days ago)
        old_ts = (datetime.now() - timedelta(days=8)).isoformat(timespec="seconds")
        db.execute(
            "INSERT INTO api_status_log (timestamp, api_indicator, api_description, claude_version, response_time_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (old_ts, "none", "Old", "1.0.18", 100),
        )
        # Insert a recent record (1 hour ago)
        recent_ts = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
        db.execute(
            "INSERT INTO api_status_log (timestamp, api_indicator, api_description, claude_version, response_time_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (recent_ts, "minor", "Recent", "1.0.19", 200),
        )
        db.commit()

        # check_now should prune old records
        body = _make_status_json("none", "All Good")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                checker.check_now()

        cursor = db.execute("SELECT COUNT(*) FROM api_status_log")
        count = cursor.fetchone()[0]
        # Old record pruned, recent + new check = 2
        assert count == 2
        db.close()


class TestVersionThrottle:
    def test_version_check_throttle(self):
        """claude --version is called at most once per 5 minutes."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("none", "OK")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20") as mock_ver:
                checker.check_now()
                checker.check_now()
                checker.check_now()

                # Should only call get_claude_version once (throttled)
                assert mock_ver.call_count == 1
        db.close()

    def test_version_check_after_throttle_expires(self):
        """After 5 min, claude --version is called again."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        body = _make_status_json("none", "OK")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20") as mock_ver:
                checker.check_now()
                assert mock_ver.call_count == 1

                # Simulate time passing (set internal timestamp back)
                checker._last_version_check = time.monotonic() - 301

                checker.check_now()
                assert mock_ver.call_count == 2
        db.close()


class TestStatusTransitions:
    def test_status_transitions(self):
        """get_status_history returns only state changes, not every check."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)
        _ensure_status_table(db)

        now = datetime.now()
        records = [
            # (minutes_ago, indicator, description)
            (60, "none", "OK"),
            (50, "none", "OK"),       # same — should be filtered
            (40, "minor", "Degraded"),  # change!
            (30, "minor", "Degraded"),  # same — filtered
            (20, "major", "Outage"),    # change!
            (10, "none", "Recovered"),  # change!
            (5, "none", "Recovered"),   # same — filtered
        ]

        for minutes_ago, indicator, desc in records:
            ts = (now - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
            db.execute(
                "INSERT INTO api_status_log (timestamp, api_indicator, api_description, claude_version, response_time_ms) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, indicator, desc, "1.0.20", 100),
            )
        db.commit()

        transitions = checker.get_status_history(hours=2)
        indicators = [t.api_indicator for t in transitions]

        # Should be: none → minor → major → none (4 transitions)
        assert indicators == ["none", "minor", "major", "none"]
        db.close()


class TestIntegration:
    def test_full_cycle(self):
        """Full cycle: check OK → check Degraded → verify get_last_status returns latest → verify get_status_history returns 2 transitions."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        # First check: OK
        body_ok = _make_status_json("none", "All Systems Operational")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body_ok)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result_ok = checker.check_now()

        assert result_ok.api_indicator == "none"

        # Reset throttle so version check runs again
        checker._last_version_check = 0

        # Second check: Degraded
        body_degraded = _make_status_json("minor", "Degraded Performance")
        with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body_degraded)):
            with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                result_degraded = checker.check_now()

        assert result_degraded.api_indicator == "minor"

        # get_last_status should return the latest (degraded)
        last = checker.get_last_status()
        assert last is not None
        assert last.api_indicator == "minor"
        assert last.api_description == "Degraded Performance"

        # get_status_history should return 2 transitions: none → minor
        transitions = checker.get_status_history(hours=24)
        indicators = [t.api_indicator for t in transitions]
        assert len(indicators) == 2
        assert indicators[0] == "none"
        assert indicators[1] == "minor"

        db.close()

    def test_haiku_error_callback_pattern(self):
        """Simulate on_api_error → check_now flow: callback calls check_now, verify result is saved."""
        db = HistoryDB(":memory:")
        db.init()
        checker = StatusChecker(db)

        captured = {}

        def on_api_error_callback():
            """Simulates what the GUI does when haiku returns an error: trigger an immediate status check."""
            body = _make_status_json("minor", "Degraded Performance")
            with patch("core.status_checker.urlopen", return_value=_mock_urlopen(body)):
                with patch("core.status_checker.get_claude_version", return_value="1.0.20"):
                    result = checker.check_now()
            captured["result"] = result

        # Trigger the callback (simulates on_api_error firing)
        on_api_error_callback()

        assert "result" in captured
        assert captured["result"].api_indicator == "minor"

        # Verify the result was actually saved to DB
        last = checker.get_last_status()
        assert last is not None
        assert last.api_indicator == "minor"
        assert last.api_description == "Degraded Performance"

        db.close()
