"""Commands: input to the chat_session use cases (ADA)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SendChatMessageCommand:
    session_id: str
    message: str


@dataclass(frozen=True)
class RefineDraftCommand:
    session_id: str
