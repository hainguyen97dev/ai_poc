"""Tests for infra/gateway_factory.py — LLM_PROVIDER resolution.

No network, no API key required: AnthropicGateway / MinimaxGateway only read
env vars in __init__ and stay lazy until .generate() is called (see their
own modules) — safe to construct in a test with nothing configured.
"""

from __future__ import annotations

import pytest

from infra.gateway_factory import get_llm_gateway
from infra.llm_gateway import AnthropicGateway
from infra.minimax_gateway import MinimaxGateway


class TestGetLlmGateway:
    def test_defaults_to_anthropic_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        assert isinstance(get_llm_gateway(), AnthropicGateway)

    def test_explicit_provider_arg_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        assert isinstance(get_llm_gateway("minimax"), MinimaxGateway)

    def test_reads_env_var_when_no_explicit_arg(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        assert isinstance(get_llm_gateway(), MinimaxGateway)

    def test_provider_name_is_case_and_whitespace_insensitive(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "  ANTHROPIC  ")
        assert isinstance(get_llm_gateway(), AnthropicGateway)

    def test_unknown_provider_raises_value_error_listing_supported(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER 'openai'"):
            get_llm_gateway()
