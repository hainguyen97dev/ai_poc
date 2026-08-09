"""Errors specific to the chat_session slice — main.py maps these to HTTP status codes."""

from __future__ import annotations


class SessionNotFoundError(Exception):
    def __init__(self, session_id: str):
        super().__init__(f"Session '{session_id}' not found")
        self.session_id = session_id


class SessionDraftUnavailableError(Exception):
    """Raised when chat/refine is attempted on a session with no COMPLETED draft to work from
    (its v1 was REJECTED or BLOCKED — nothing for the SA to discuss or refine)."""

    def __init__(self, session_id: str, detail: str):
        super().__init__(detail)
        self.session_id = session_id
        self.detail = detail
