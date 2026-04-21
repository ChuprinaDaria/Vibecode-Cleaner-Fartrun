"""Tests for plugin base class."""

import pytest
from core.plugin import Plugin, Alert


def test_alert_creation():
    alert = Alert(
        source="test",
        severity="critical",
        title="Test Alert",
        message="Something broke",
    )
    assert alert.source == "test"
    assert alert.severity == "critical"
    assert alert.title == "Test Alert"


def test_plugin_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Plugin()


def test_plugin_subclass_must_implement_all():
    class IncompletePlugin(Plugin):
        name = "incomplete"
        icon = "?"

    with pytest.raises(TypeError):
        IncompletePlugin()
