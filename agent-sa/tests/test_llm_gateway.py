"""Tests for AnthropicGateway.generate_with_reasoning — no real network: the
`anthropic` SDK client is replaced with a fake that returns canned content
blocks shaped like the real extended-thinking response (thinking + text
blocks, in that order). See infra/llm_gateway.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pytest

import infra.llm_gateway as llm_gateway_module
from infra.llm_gateway import AnthropicGateway


@dataclass
class FakeBlock:
    type: str
    thinking: str = ""
    text: str = ""


class FakeMessage:
    def __init__(self, content: List[FakeBlock]):
        self.content = content


class FakeMessagesResource:
    def __init__(self, response: FakeMessage):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class FakeAnthropicClient:
    def __init__(self, response: FakeMessage, api_key=None):
        self.messages = FakeMessagesResource(response)


@pytest.fixture
def fake_anthropic(monkeypatch):
    """Returns a factory: call it with the FakeMessage the fake client should
    return, get back the client instance the gateway will use."""
    holder = {}

    def factory(response: FakeMessage):
        client = FakeAnthropicClient(response)
        holder["client"] = client
        monkeypatch.setattr(llm_gateway_module, "Anthropic", lambda api_key: client)
        return client

    return factory


def test_generate_with_reasoning_separates_thinking_from_text(fake_anthropic):
    response = FakeMessage(
        [
            FakeBlock(type="thinking", thinking="On-premise rules out AWS API Gateway."),
            FakeBlock(type="text", text="Use Kong."),
        ]
    )
    fake_anthropic(response)
    gateway = AnthropicGateway(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")

    result = gateway.generate_with_reasoning("system", "user")

    assert result.content == "Use Kong."
    assert result.reasoning == "On-premise rules out AWS API Gateway."


def test_generate_with_reasoning_requests_thinking_with_a_valid_token_budget(fake_anthropic):
    response = FakeMessage([FakeBlock(type="text", text="Use Kong.")])
    client = fake_anthropic(response)
    gateway = AnthropicGateway(
        api_key="sk-ant-test", model="claude-3-5-sonnet-20241022", max_tokens=100, thinking_budget_tokens=2000
    )

    gateway.generate_with_reasoning("system", "user")

    kwargs = client.messages.last_kwargs
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 2000}
    # max_tokens must exceed budget_tokens, even though the configured
    # gateway max_tokens (100) alone would violate that.
    assert kwargs["max_tokens"] > 2000


def test_generate_with_reasoning_is_none_without_a_thinking_block(fake_anthropic):
    response = FakeMessage([FakeBlock(type="text", text="Use Kong.")])
    fake_anthropic(response)
    gateway = AnthropicGateway(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")

    result = gateway.generate_with_reasoning("system", "user")

    assert result.reasoning is None


def test_generate_with_reasoning_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    gateway = AnthropicGateway(api_key=None, model="claude-3-5-sonnet-20241022")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        gateway.generate_with_reasoning("system", "user")
