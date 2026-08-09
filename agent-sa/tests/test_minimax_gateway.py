"""Tests for MinimaxGateway — no real network: httpx.MockTransport stands in
for the MiniMax API. Covers the generate()/generate_with_reasoning() refactor
that shares _request() under the hood.
"""

from __future__ import annotations

import httpx
import pytest

from infra.minimax_gateway import MinimaxGateway


@pytest.fixture(autouse=True)
def route_httpx_post_through_mock_transport(monkeypatch):
    """MinimaxGateway calls the bare `httpx.post(...)` function, not a client
    instance — patch it to dispatch through a real httpx.Client bound to a
    MockTransport (not a hand-built Response), so response.raise_for_status()
    sees a properly linked request/response pair like it would in production."""
    handler_box = {}

    def fake_post(url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(handler_box["handler"])) as client:
            return client.post(url, **kwargs)

    monkeypatch.setattr("infra.minimax_gateway.httpx.post", fake_post)
    yield handler_box


def _install(route_box, handler):
    route_box["handler"] = handler


def test_generate_returns_plain_content(route_httpx_post_through_mock_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"base_resp": {"status_code": 0}, "choices": [{"message": {"content": "Use Kong."}}]})

    _install(route_httpx_post_through_mock_transport, handler)
    gateway = MinimaxGateway(model="MiniMax-M2.7", api_key="test-key")

    assert gateway.generate("system", "user") == "Use Kong."


def test_generate_with_reasoning_captures_reasoning_content(route_httpx_post_through_mock_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0},
                "choices": [{"message": {"content": "Use Kong.", "reasoning_content": "On-premise rules out AWS."}}],
            },
        )

    _install(route_httpx_post_through_mock_transport, handler)
    gateway = MinimaxGateway(model="MiniMax-M2.7", api_key="test-key")

    result = gateway.generate_with_reasoning("system", "user")

    assert result.content == "Use Kong."
    assert result.reasoning == "On-premise rules out AWS."


def test_generate_with_reasoning_is_none_when_model_omits_it(route_httpx_post_through_mock_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"base_resp": {"status_code": 0}, "choices": [{"message": {"content": "Use Kong."}}]})

    _install(route_httpx_post_through_mock_transport, handler)
    gateway = MinimaxGateway(model="MiniMax-M2.7", api_key="test-key")

    result = gateway.generate_with_reasoning("system", "user")

    assert result.content == "Use Kong."
    assert result.reasoning is None


def test_application_level_error_raises_before_reasoning_is_parsed(route_httpx_post_through_mock_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"base_resp": {"status_code": 1004, "status_msg": "auth failed"}})

    _install(route_httpx_post_through_mock_transport, handler)
    gateway = MinimaxGateway(model="MiniMax-M2.7", api_key="test-key")

    with pytest.raises(RuntimeError, match="auth failed"):
        gateway.generate_with_reasoning("system", "user")
