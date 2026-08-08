"""Shared pytest fixtures for the AIA suite (tests/) and the shared kernel.

Living at the package root (not inside tests/) makes pytest treat `agent-sa/`
itself as the import rootdir — the same directory agent.py runs from — so
tests can `import domain`, `import features`, `import infra` exactly like
the CLI adapter does. No sys.path hacking needed here (contrast with
ada-service/conftest.py, which needs one because it sits a directory deeper
and its own `features` package collides by name with this one — see the
comment there).
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from infra.event_bus import EventBus


class FakeLlmGateway:
    """Stand-in for domain.ports.LlmGateway — no network, deterministic output.

    Records every call so tests can assert the model *was* invoked (normal
    path) or, just as importantly, *wasn't* (blocked/rejected input must
    short-circuit in validation before ever reaching the gateway).
    """

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
