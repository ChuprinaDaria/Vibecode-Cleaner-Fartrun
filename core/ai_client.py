"""Multi-provider AI client for tips, explanations, and prompt building.

Supports:
- anthropic: Claude Haiku (default)
- openai: Any OpenAI-compatible endpoint (DeepSeek, OpenRouter, NVIDIA NIM, Azure)

Provider selection via config [ai] section or env vars.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time

log = logging.getLogger(__name__)

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"

DEFAULT_MODELS = {
    PROVIDER_ANTHROPIC: "claude-haiku-4-5-20251001",
    PROVIDER_OPENAI: "gpt-4o-mini",
}

DEFAULT_BASE_URLS = {
    PROVIDER_OPENAI: "https://api.openai.com/v1",
}

# Well-known provider shortcuts → base_url
KNOWN_PROVIDERS = {
    "deepseek": "https://api.deepseek.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "huggingface": "https://router.huggingface.co/v1",
}


def _resolve_config(config: dict | None) -> dict:
    """Extract [ai] section from config with fallback to [haiku] for compat."""
    if not config:
        return {}
    if "ai" in config:
        return config["ai"]
    if "haiku" in config:
        return {"provider": "anthropic", "api_key": config["haiku"].get("api_key", "")}
    return {}


class AIClient:
    """Universal AI client with caching and rate limiting."""

    def __init__(
        self,
        api_key: str | None = None,
        config: dict | None = None,
        on_api_error=None,
    ):
        ai_conf = _resolve_config(config)
        self._provider = ai_conf.get("provider", PROVIDER_ANTHROPIC)
        self._model = ai_conf.get("model") or self._default_model()

        # Base URL must be set before _env_key() which inspects it
        self._base_url = ai_conf.get("base_url") or self._default_base_url()

        # Resolve API key: explicit → env → config
        resolved = api_key or self._env_key() or ai_conf.get("api_key")
        self._api_key = resolved if resolved else None

        self._cache: dict[str, str] = {}
        self._last_call: float = 0
        self._min_interval: int = 5
        self._client = None
        self._on_api_error = on_api_error

    def _env_key(self) -> str | None:
        """Resolve API key from environment based on provider."""
        if self._provider == PROVIDER_ANTHROPIC:
            return os.environ.get("ANTHROPIC_API_KEY")
        # OpenAI-compatible: check provider-specific first, then generic
        for var in self._env_key_names():
            val = os.environ.get(var)
            if val:
                return val
        return None

    def _env_key_names(self) -> list[str]:
        """Env var names to check for API key, in priority order."""
        provider = self._provider
        base_url = self._base_url or ""
        names = []
        if "deepseek" in base_url:
            names.append("DEEPSEEK_API_KEY")
        if "openrouter" in base_url:
            names.append("OPENROUTER_API_KEY")
        if "nvidia" in base_url:
            names.append("NVIDIA_API_KEY")
        if "azure" in base_url or "cognitiveservices" in base_url:
            names.append("AZURE_API_KEY")
        if "huggingface" in base_url:
            names.append("HF_API_KEY")
            names.append("HUGGINGFACE_API_KEY")
        if provider == PROVIDER_OPENAI:
            names.append("OPENAI_API_KEY")
        return names

    def _default_model(self) -> str:
        return DEFAULT_MODELS.get(self._provider, DEFAULT_MODELS[PROVIDER_OPENAI])

    def _default_base_url(self) -> str | None:
        # Check known provider shortcuts
        for name, url in KNOWN_PROVIDERS.items():
            if name in self._provider:
                return url
        return DEFAULT_BASE_URLS.get(self._provider)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return self._api_key is not None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            return None

        if self._provider == PROVIDER_ANTHROPIC:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                log.warning("anthropic SDK not installed — AI features disabled")
                self._api_key = None
        else:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except ImportError:
                log.warning("openai SDK not installed — AI features disabled")
                self._api_key = None

        return self._client

    def ask(self, prompt: str, max_tokens: int = 200) -> str | None:
        """Send prompt to configured provider. Returns cached response if available."""
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
            result = self._call(client, prompt, max_tokens)
            if result:
                self._cache[cache_key] = result
                self._last_call = now
            return result
        except Exception as e:
            log.error("AI API error (%s): %s", self._provider, e)
            if self._on_api_error:
                self._on_api_error(str(e))
            return None

    def _call(self, client, prompt: str, max_tokens: int) -> str | None:
        """Provider-specific API call."""
        if self._provider == PROVIDER_ANTHROPIC:
            response = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            response = client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content

    def batch_explain(
        self, items: list[str], context: str, language: str
    ) -> dict[str, str]:
        """Explain multiple items in one API call."""
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
