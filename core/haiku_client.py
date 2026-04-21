"""Claude Haiku client for personalized tips and explanations.

Optional — requires anthropic SDK and API key.
~$0.001 per call, rate limited to max 1 call per 30 seconds.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time

log = logging.getLogger(__name__)


class HaikuClient:
    def __init__(self, api_key: str | None = None, config: dict | None = None, on_api_error=None):
        # Resolution: explicit param → env var → config dict → None
        resolved = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved and config:
            resolved = config.get("haiku", {}).get("api_key") or None
        # Empty string counts as None
        self._api_key = resolved if resolved else None
        self._cache: dict[str, str] = {}
        self._last_call: float = 0
        self._min_interval: int = 5
        self._client = None
        self._on_api_error = on_api_error

    def is_available(self) -> bool:
        return self._api_key is not None

    def _get_client(self):
        if self._client is None and self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                log.warning("anthropic SDK not installed — Haiku features disabled")
                self._api_key = None
        return self._client

    def ask(self, prompt: str, max_tokens: int = 200) -> str | None:
        """Ask Haiku a question. Returns cached response if available."""
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.is_available():
            return None

        now = time.time()
        if now - self._last_call < self._min_interval:
            return None

        client = self._get_client()
        if not client:
            return None

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            result = response.content[0].text
            self._cache[cache_key] = result
            self._last_call = now
            return result
        except Exception as e:
            log.error("Haiku API error: %s", e)
            if self._on_api_error:
                self._on_api_error(str(e))
            return None

    def batch_explain(
        self, items: list[str], context: str, language: str
    ) -> dict[str, str]:
        """Explain multiple items in one API call.

        Returns a dict mapping each item to its explanation.
        Returns empty dict if no items or client not available.
        """
        if not items or not self.is_available():
            return {}

        numbered = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
        prompt = (
            f"You are a developer assistant. Explain each of the following findings "
            f"in plain human language ({language}). Keep each explanation to 1-2 sentences. "
            f"Context: {context}\n\n"
            f"Findings:\n{numbered}\n\n"
            f"Reply with the same numbered list, one explanation per line. "
            f"Format: '1. explanation', '2. explanation', etc."
        )

        response = self.ask(prompt, max_tokens=600)
        if not response:
            return {}

        # Build index map: 1-based number → item
        index_map = {i + 1: item for i, item in enumerate(items)}

        result: dict[str, str] = {}
        for line in response.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^(\d+)\.\s*(.+)", line)
            if m:
                num = int(m.group(1))
                explanation = m.group(2).strip()
                if num in index_map:
                    result[index_map[num]] = explanation

        return result

    def get_tip(self, stats_summary: str) -> str | None:
        """Get personalized tip based on usage stats."""
        prompt = (
            f"You are a Claude Code usage advisor. Based on these stats, give ONE specific, "
            f"actionable tip to save tokens or improve efficiency. Max 2 sentences.\n\n"
            f"Stats: {stats_summary}"
        )
        return self.ask(prompt)

