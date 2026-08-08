"""Fixtures for ADA's handler tests — same shape as the root conftest.py's,
duplicated (not imported) because this suite runs in its own pytest process
(see ../conftest.py's docstring for why).
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from infra.event_bus import EventBus


class FakeLlmGateway:
    def __init__(self, response: str = "", available: bool = True):
        self.response = response
        self._available = available
        self.calls: List[Tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response

    def is_available(self) -> bool:
        return self._available


@pytest.fixture
def fake_llm() -> FakeLlmGateway:
    return FakeLlmGateway()


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()
