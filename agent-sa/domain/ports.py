"""Ports — interfaces the domain/features depend on; infra provides the implementation.

Dependency inversion: handlers depend on `LlmGateway` (this file), never on
`anthropic` directly. infra/llm_gateway.py implements it.
"""

from __future__ import annotations

from typing import Protocol


class LlmGateway(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's completion text for the given prompts."""
        ...

    def is_available(self) -> bool:
        """Whether a real call can be made (package installed + API key present)."""
        ...
