"""Anthropic-backed implementation of domain.ports.LlmGateway."""

from __future__ import annotations

import os
from typing import Optional

try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via --dry-run / is_available()
    ANTHROPIC_AVAILABLE = False


class AnthropicGateway:
    """Implements domain.ports.LlmGateway using the Anthropic API.

    Config precedence: explicit constructor arg > env var > hardcoded default.
    Env vars are read here, not in the adapter (agent.py / main.py) — see .env.example.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
    ):
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.max_tokens = max_tokens or int(os.getenv("ANTHROPIC_MAX_TOKENS", "4000"))
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and bool(self._api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package not installed. Install with: pip install anthropic")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set. export ANTHROPIC_API_KEY=sk-ant-...")

        client = Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text
