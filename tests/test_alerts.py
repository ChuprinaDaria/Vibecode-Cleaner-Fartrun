"""Tests for alert system."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from core.alerts import AlertManager
from core.plugin import Alert


@pytest.fixture
def mock_platform():
    p = MagicMock()
    return p


@pytest.fixture
def manager(mock_platform):
    config = {
        "sounds": {"enabled": True, "mode": "classic",
                    "quiet_hours_start": "23:00", "quiet_hours_end": "07:00"},
        "alerts": {
            "cooldown_seconds": 5,
            "desktop_notifications": True,
        },
    }
    with patch("core.alerts.get_platform", return_value=mock_platform):
        return AlertManager(config)


def test_deduplication(manager):
    alert = Alert(source="docker", severity="critical", title="down", message="container crashed")
    assert manager.should_fire(alert) is True
    manager.mark_fired(alert)
    assert manager.should_fire(alert) is False


def test_dedup_key(manager):
    a1 = Alert(source="docker", severity="critical", title="down", message="msg1")
    a2 = Alert(source="docker", severity="critical", title="down", message="msg2 different")
    manager.mark_fired(a1)
    assert manager.should_fire(a2) is False


def test_different_alerts_not_deduplicated(manager):
    a1 = Alert(source="docker", severity="critical", title="down", message="msg")
    a2 = Alert(source="docker", severity="warning", title="cpu high", message="msg")
    manager.mark_fired(a1)
    assert manager.should_fire(a2) is True


def test_quiet_hours(manager):
    with patch("core.alerts.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 4, 14, 2, 0, 0)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        assert manager.is_quiet_hours() is True

    with patch("core.alerts.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 4, 14, 12, 0, 0)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        assert manager.is_quiet_hours() is False


def test_send_desktop_uses_platform(manager, mock_platform):
    alert = Alert(source="docker", severity="critical", title="Container down", message="nginx crashed")
    manager.send_desktop(alert)
    mock_platform.notify.assert_called_once()
    call_args = mock_platform.notify.call_args[0]
    assert "docker" in call_args[0]
    assert "nginx crashed" in call_args[1]


def test_no_sound_in_quiet_hours(manager, mock_platform):
    with patch.object(manager, "is_quiet_hours", return_value=True):
        alert = Alert(source="docker", severity="critical", title="down", message="msg")
        manager.play_sound(alert)
        mock_platform.play_sound.assert_not_called()


def test_sound_disabled_skips(mock_platform):
    config = {
        "sounds": {"enabled": False, "mode": "classic"},
        "alerts": {"cooldown_seconds": 0, "desktop_notifications": False},
    }
    with patch("core.alerts.get_platform", return_value=mock_platform):
        mgr = AlertManager(config)
    alert = Alert(source="test", severity="warning", title="T", message="M")
    mgr.play_sound(alert)
    mock_platform.play_sound.assert_not_called()


def test_process_fires_and_deduplicates(manager, mock_platform):
    # Warning: fires but no desktop notify (only critical/high get desktop)
    alert = Alert(source="test", severity="warning", title="T", message="M")
    assert manager.process(alert) is True
    mock_platform.notify.assert_not_called()
    # Second time should be deduplicated
    assert manager.process(alert) is False


def test_process_critical_sends_desktop(manager, mock_platform):
    alert = Alert(source="test", severity="critical", title="T", message="M")
    assert manager.process(alert) is True
    mock_platform.notify.assert_called_once()


def test_dismiss_suppresses_future_alerts(manager, mock_platform):
    alert = Alert(source="test", severity="critical", title="T", message="M")
    manager.dismiss(alert)
    assert manager.process(alert) is False


def test_dismiss_all(manager, mock_platform):
    a1 = Alert(source="test", severity="critical", title="A", message="M")
    a2 = Alert(source="test", severity="warning", title="B", message="M")
    manager.process(a1)
    manager.dismiss_all()
    # dismiss_all blocks everything — even new alerts never seen before
    assert manager.process(a2) is False
    # And previously seen ones too
    manager._fired.clear()
    assert manager.process(a1) is False
