"""Ports — interfaces the domain/features depend on; infra provides the implementation.

Dependency inversion: handlers depend on `LlmGateway` (this file), never on
`anthropic` directly. infra/llm_gateway.py implements it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from .session import ChatMessage, DraftVersionRecord, Session, UsageStats


@dataclass(frozen=True)
class LlmResult:
    """Return type of LlmGateway.generate_with_reasoning."""

    content: str
    # The model's extended-thinking/reasoning trace, when the provider exposes
    # one for this call. None for providers/models that don't support it —
    # callers must treat this as always-optional, never assume it's present.
    reasoning: Optional[str] = None


class LlmGateway(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's completion text for the given prompts."""
        ...

    def is_available(self) -> bool:
        """Whether a real call can be made (package installed + API key present)."""
        ...

    def generate_with_reasoning(self, system_prompt: str, user_prompt: str) -> LlmResult:
        """Like generate(), but also surfaces the model's reasoning trace when
        available (LlmResult.reasoning is None otherwise). Used wherever the
        caller wants to show reasoning to the user — features/chat_session and
        ADA's three task-type handlers. generate() is untouched and remains
        the plain-text call the AIA CLI (agent.py) uses."""
        ...


class SessionRepository(Protocol):
    """Persists the chat/draft-version timeline layered above analysis runs.

    infra/session_store.py implements this against SQLite. See domain/session.py
    for why this sits outside the ChangeRequestAnalysis aggregate.
    """

    def create_session(
        self,
        session_id: str,
        *,
        task_type: str,
        requirement_id: Optional[str],
        subject_ref: str,
        request_json: str,
    ) -> Session:
        """Create the session shell (v1's draft is added separately via add_draft_version)."""
        ...

    def add_draft_version(
        self,
        session_id: str,
        *,
        analysis_id: str,
        status: str,
        content: str,
        assumptions_count: int,
        questions_count: int,
        risks_count: int,
        reasoning: Optional[str] = None,
    ) -> DraftVersionRecord:
        """Append the next version (v1 on session creation, vN+1 on each refine)."""
        ...

    def add_message(
        self, session_id: str, role: str, content: str, *, reasoning: Optional[str] = None
    ) -> ChatMessage:
        ...

    def get_session(self, session_id: str) -> Optional[Session]:
        ...

    def list_sessions(self) -> Sequence[Session]:
        """Most-recently-updated first."""
        ...

    def get_usage_stats(self) -> UsageStats:
        """Count of LLM-invoking requests actually made so far, by kind."""
        ...
