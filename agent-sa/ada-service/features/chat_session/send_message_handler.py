"""Handler for SendChatMessage — ADA's conversational reply, grounded in the
session's latest draft and prior chat history.

Deliberately does NOT create a new draft version — that only happens via
RefineDraftHandler (refine_draft_handler.py), triggered by a separate,
explicit SA action. See docs/superpowers/specs/2026-08-09-ada-chat-session-design.md.
"""

from __future__ import annotations

from domain.ports import LlmGateway, SessionRepository
from domain.session import ChatMessage, Session

from .command import SendChatMessageCommand
from .errors import SessionDraftUnavailableError, SessionNotFoundError


def _build_chat_prompt(session: Session, user_message: str) -> str:
    latest = session.latest_version
    draft_str = latest.content if latest else "[No draft yet]"
    version_label = f"v{latest.version_no}" if latest else "none"
    history_lines = [f"{m.role.upper()}: {m.content}" for m in session.messages]
    history_str = "\n\n".join(history_lines) if history_lines else "[No prior messages]"

    return f"""
TASK: Answer the Solution Architect's follow-up question about the draft below.
Reply conversationally and concisely. Do NOT rewrite the full draft here — the
SA will trigger a separate "Refine draft" action when ready for that.

LATEST DRAFT ({version_label}):
{draft_str}

CONVERSATION SO FAR:
{history_str}

SOLUTION ARCHITECT: {user_message}
"""


class SendChatMessageHandler:
    def __init__(self, llm: LlmGateway, system_prompt: str, sessions: SessionRepository):
        self._llm = llm
        self._system_prompt = system_prompt
        self._sessions = sessions

    def handle(self, cmd: SendChatMessageCommand) -> ChatMessage:
        session = self._sessions.get_session(cmd.session_id)
        if session is None:
            raise SessionNotFoundError(cmd.session_id)

        latest = session.latest_version
        if latest is None or latest.status != "COMPLETED":
            raise SessionDraftUnavailableError(
                cmd.session_id,
                f"Session '{cmd.session_id}' has no completed draft to chat about "
                f"(latest status: {latest.status if latest else 'NONE'})",
            )

        prompt = _build_chat_prompt(session, cmd.message)
        self._sessions.add_message(cmd.session_id, "user", cmd.message)
        result = self._llm.generate_with_reasoning(self._system_prompt, prompt)
        return self._sessions.add_message(
            cmd.session_id, "assistant", result.content, reasoning=result.reasoning
        )
