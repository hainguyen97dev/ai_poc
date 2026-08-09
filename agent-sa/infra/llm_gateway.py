"""Anthropic-backed implementation of domain.ports.LlmGateway."""

from __future__ import annotations

import os
from typing import Optional

from domain.ports import LlmResult

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
        thinking_budget_tokens: Optional[int] = None,
    ):
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.max_tokens = max_tokens or int(os.getenv("ANTHROPIC_MAX_TOKENS", "4000"))
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        # Only spent when generate_with_reasoning() is called (extended thinking).
        # Must be < the max_tokens used for that call — see generate_with_reasoning.
        self._thinking_budget_tokens = thinking_budget_tokens or int(
            os.getenv("ANTHROPIC_THINKING_BUDGET_TOKENS", "2000")
        )

    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and bool(self._api_key)

    def _require_ready(self) -> None:
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package not installed. Install with: pip install anthropic")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set. export ANTHROPIC_API_KEY=sk-ant-...")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self._require_ready()
        client = Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    def generate_with_reasoning(self, system_prompt: str, user_prompt: str) -> LlmResult:
        self._require_ready()
        client = Anthropic(api_key=self._api_key)
        # Extended thinking requires max_tokens > budget_tokens; bump the
        # request's max_tokens (not self.max_tokens) if needed, leaving room
        # for the actual answer after the thinking budget is spent.
        max_tokens = max(self.max_tokens, self._thinking_budget_tokens + 1024)
        message = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "enabled", "budget_tokens": self._thinking_budget_tokens},
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # With thinking enabled, content is a mix of "thinking" and "text"
        # blocks (in that order) rather than a single text block — see
        # https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking.
        reasoning_parts = [block.thinking for block in message.content if block.type == "thinking"]
        text_parts = [block.text for block in message.content if block.type == "text"]
        return LlmResult(
            content="".join(text_parts),
            reasoning="\n\n".join(reasoning_parts) or None,
        )
