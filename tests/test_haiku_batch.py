"""Tests for HaikuClient batch_explain and config support."""

from core.haiku_client import HaikuClient


def test_batch_explain_no_key_returns_empty():
    """Client with no key returns empty dict."""
    client = HaikuClient(api_key=None)
    result = client.batch_explain(["item1", "item2"], context="test", language="en")
    assert result == {}


def test_batch_explain_empty_items_returns_empty():
    """Empty items list returns empty dict."""
    client = HaikuClient(api_key="sk-ant-test")
    result = client.batch_explain([], context="test", language="en")
    assert result == {}


def test_batch_explain_parses_response(monkeypatch):
    client = HaikuClient(api_key="sk-ant-test")
    client._min_interval = 0
    monkeypatch.setattr(client, "ask", lambda prompt, **kw: "1. first explanation\n2. second explanation\n")
    result = client.batch_explain(["foo", "bar"], context="ctx", language="en")
    assert result == {"foo": "first explanation", "bar": "second explanation"}


def test_config_fallback():
    """Client reads api_key from config dict param."""
    config = {"haiku": {"api_key": "sk-ant-from-config"}}
    client = HaikuClient(config=config)
    assert client.is_available()
    assert client._api_key == "sk-ant-from-config"


def test_config_fallback_empty():
    """Empty string key in config means not available."""
    config = {"haiku": {"api_key": ""}}
    client = HaikuClient(config=config)
    assert not client.is_available()


def test_rate_limit_default_5s():
    """_min_interval is 5 seconds."""
    client = HaikuClient(api_key="sk-ant-test")
    assert client._min_interval == 5
