"""Fixtures for ADA's handler tests — same shape as the root conftest.py's,
duplicated (not imported) because this suite runs in its own pytest process
(see ../conftest.py's docstring for why).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pytest

from domain.ports import LlmResult
from infra.event_bus import EventBus


class FakeLlmGateway:
    def __init__(self, response: str = "", available: bool = True, reasoning: Optional[str] = None):
        self.response = response
        self.reasoning = reasoning
        self._available = available
        self.calls: List[Tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response

    def generate_with_reasoning(self, system_prompt: str, user_prompt: str) -> LlmResult:
        self.calls.append((system_prompt, user_prompt))
        return LlmResult(content=self.response, reasoning=self.reasoning)

    def is_available(self) -> bool:
        return self._available


@pytest.fixture
def fake_llm() -> FakeLlmGateway:
    return FakeLlmGateway()


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()
