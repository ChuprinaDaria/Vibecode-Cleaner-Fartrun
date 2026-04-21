"""Tests for Haiku client."""

from core.haiku_client import HaikuClient


def test_client_disabled_without_key():
    client = HaikuClient(api_key=None)
    assert not client.is_available()


def test_client_enabled_with_key():
    client = HaikuClient(api_key="sk-ant-test-key")
    assert client.is_available()


def test_ask_returns_cached():
    client = HaikuClient(api_key="sk-ant-test")
    client._cache["098f6bcd4621d373cade4e832627b4f6"] = "cached_response"
    # md5 of "test" = 098f6bcd4621d373cade4e832627b4f6
    result = client.ask("test")
    assert result == "cached_response"


def test_ask_returns_none_without_key():
    client = HaikuClient(api_key=None)
    result = client.ask("some prompt")
    assert result is None


def test_rate_limiting():
    import time
    client = HaikuClient(api_key="sk-ant-test")
    client._last_call = time.time()  # just called
    # Should return None due to rate limit (no actual API call)
    result = client.ask("prompt that is not cached")
    assert result is None


def test_on_api_error_callback():
    from unittest.mock import MagicMock, patch

    callback = MagicMock()
    client = HaikuClient(api_key="sk-ant-test", on_api_error=callback)
    # Bypass rate limit
    client._last_call = 0

    mock_anthropic_client = MagicMock()
    mock_anthropic_client.messages.create.side_effect = Exception("connection timeout")
    client._client = mock_anthropic_client

    result = client.ask("test prompt")
    assert result is None
    callback.assert_called_once_with("connection timeout")


def test_on_api_error_not_called_on_success():
    from unittest.mock import MagicMock

    callback = MagicMock()
    client = HaikuClient(api_key="sk-ant-test", on_api_error=callback)
    client._last_call = 0

    mock_anthropic_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="great answer")]
    mock_anthropic_client.messages.create.return_value = mock_response
    client._client = mock_anthropic_client

    result = client.ask("test prompt")
    assert result == "great answer"
    callback.assert_not_called()
