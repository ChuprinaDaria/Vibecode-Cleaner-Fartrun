"""Backward-compatible wrapper around AIClient.

All new code should use core.ai_client.AIClient directly.
This module exists so existing imports keep working.
"""

from __future__ import annotations

from core.ai_client import AIClient


class HaikuClient(AIClient):
    """Drop-in replacement: forces provider=anthropic when only api_key is given."""

    def __init__(self, api_key: str | None = None, config: dict | None = None, on_api_error=None):
        if config is None and api_key is not None:
            config = {"ai": {"provider": "anthropic", "api_key": api_key}}
        super().__init__(api_key=api_key, config=config, on_api_error=on_api_error)
