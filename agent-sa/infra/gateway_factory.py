"""Picks which LlmGateway adapter to wire up, based on LLM_PROVIDER in .env.

This is the one place that knows about all adapters. Handlers/features only
ever depend on domain.ports.LlmGateway — see spec/domain-model.md § Sharing Rules
("domain/ and infra/ are shared by both apps").
"""

from __future__ import annotations

import os

from domain.ports import LlmGateway

from .llm_gateway import AnthropicGateway
from .minimax_gateway import MinimaxGateway

_PROVIDERS = {
    "anthropic": AnthropicGateway,
    "minimax": MinimaxGateway,
}


def get_llm_gateway(provider: str | None = None) -> LlmGateway:
    """Build the configured LlmGateway. Reads LLM_PROVIDER from the environment
    if `provider` isn't passed explicitly (defaults to "anthropic")."""
    name = (provider or os.getenv("LLM_PROVIDER", "anthropic")).strip().lower()
    try:
        gateway_cls = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{name}'. Supported: {', '.join(sorted(_PROVIDERS))}"
        ) from None
    return gateway_cls()
