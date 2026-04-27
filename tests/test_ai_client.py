"""Tests for multi-provider AIClient."""

from unittest.mock import MagicMock

from core.ai_client import AIClient, PROVIDER_ANTHROPIC, PROVIDER_OPENAI


# --- Provider resolution ---

def test_default_provider_is_anthropic():
    client = AIClient(api_key="test")
    assert client.provider == PROVIDER_ANTHROPIC


def test_openai_provider_from_config():
    client = AIClient(config={"ai": {"provider": "openai", "api_key": "sk-test"}})
    assert client.provider == PROVIDER_OPENAI


def test_fallback_from_haiku_config():
    client = AIClient(config={"haiku": {"api_key": "sk-ant-test"}})
    assert client.provider == PROVIDER_ANTHROPIC
    assert client.is_available()


def test_deepseek_base_url():
    client = AIClient(config={"ai": {
        "provider": "openai",
        "api_key": "sk-ds",
        "base_url": "https://api.deepseek.com",
    }})
    assert client._base_url == "https://api.deepseek.com"


def test_openrouter_base_url():
    client = AIClient(config={"ai": {
        "provider": "openai",
        "api_key": "sk-or",
        "base_url": "https://openrouter.ai/api/v1",
    }})
    assert client._base_url == "https://openrouter.ai/api/v1"


def test_nvidia_base_url():
    client = AIClient(config={"ai": {
        "provider": "openai",
        "api_key": "nvapi-test",
        "base_url": "https://integrate.api.nvidia.com/v1",
    }})
    assert client._base_url == "https://integrate.api.nvidia.com/v1"


def test_huggingface_base_url():
    client = AIClient(config={"ai": {
        "provider": "openai",
        "api_key": "hf_test",
        "base_url": "https://router.huggingface.co/v1",
    }})
    assert client._base_url == "https://router.huggingface.co/v1"


def test_custom_model():
    client = AIClient(config={"ai": {
        "provider": "openai",
        "api_key": "test",
        "model": "deepseek-coder",
    }})
    assert client.model == "deepseek-coder"


def test_disabled_without_key():
    client = AIClient()
    assert not client.is_available()


def test_enabled_with_key():
    client = AIClient(api_key="test-key")
    assert client.is_available()


# --- Caching ---

def test_ask_returns_cached():
    client = AIClient(api_key="test")
    client._cache["098f6bcd4621d373cade4e832627b4f6"] = "cached"
    assert client.ask("test") == "cached"


def test_ask_returns_none_without_key():
    client = AIClient()
    assert client.ask("prompt") is None


# --- Rate limiting ---

def test_rate_limiting():
    import time
    client = AIClient(api_key="test")
    client._last_call = time.time()
    assert client.ask("not cached") is None


# --- OpenAI-compatible call path ---

def test_openai_call_path():
    client = AIClient(config={"ai": {
        "provider": "openai",
        "api_key": "sk-test",
        "model": "gpt-4o-mini",
    }})
    client._last_call = 0

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "openai response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    client._client = mock_client

    result = client.ask("test prompt")
    assert result == "openai response"
    mock_client.chat.completions.create.assert_called_once()


# --- Anthropic call path ---

def test_anthropic_call_path():
    client = AIClient(api_key="sk-ant-test")
    client._last_call = 0

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="claude response")]
    mock_client.messages.create.return_value = mock_response
    client._client = mock_client

    result = client.ask("test prompt")
    assert result == "claude response"
    mock_client.messages.create.assert_called_once()


# --- Error callback ---

def test_error_callback_called():
    callback = MagicMock()
    client = AIClient(api_key="test", on_api_error=callback)
    client._last_call = 0

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("timeout")
    client._client = mock_client

    result = client.ask("prompt")
    assert result is None
    callback.assert_called_once_with("timeout")


# --- batch_explain ---

def test_batch_explain_empty_without_key():
    client = AIClient()
    assert client.batch_explain(["item"], "ctx", "en") == {}


def test_batch_explain_empty_items():
    client = AIClient(api_key="test")
    assert client.batch_explain([], "ctx", "en") == {}


# --- HaikuClient backward compat ---

def test_haiku_client_compat():
    from core.haiku_client import HaikuClient
    client = HaikuClient(api_key="sk-ant-test")
    assert client.is_available()
    assert client.provider == PROVIDER_ANTHROPIC


def test_haiku_client_config_compat():
    from core.haiku_client import HaikuClient
    client = HaikuClient(config={"haiku": {"api_key": "sk-ant-test"}})
    assert client.is_available()
    assert client.provider == PROVIDER_ANTHROPIC
