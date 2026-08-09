"""Tests for the chat_session slice — SendChatMessageHandler and RefineDraftHandler.

Uses a real SqliteSessionRepository (temp file) rather than a fake, same
choice as tests/test_session_store.py: cheap enough and exercises the actual
persistence round-trip the handlers depend on (latest_version, request_json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from features.chat_session.command import RefineDraftCommand, SendChatMessageCommand
from features.chat_session.errors import SessionDraftUnavailableError, SessionNotFoundError
from features.chat_session.refine_draft_handler import RefineDraftHandler
from features.chat_session.send_message_handler import SendChatMessageHandler
from infra.session_store import SqliteSessionRepository

SYSTEM_PROMPT = "You are the Architecture Decision Assistant."


@pytest.fixture
def sessions(tmp_path: Path) -> SqliteSessionRepository:
    return SqliteSessionRepository(tmp_path / "sessions.db")


def _seed_completed_session(sessions: SqliteSessionRepository, *, session_id="ADA-001", request_fields=None) -> None:
    sessions.create_session(
        session_id,
        task_type="draft_adr",
        requirement_id=None,
        subject_ref="API Gateway Pattern",
        request_json=json.dumps(
            request_fields
            or {
                "decision_title": "API Gateway Pattern",
                "options_to_evaluate": ["Kong", "AWS API Gateway"],
                "constraints": ["On-premise deployment required"],
                "current_architecture": None,
                "requirement_id": None,
                "conversation_context": None,
            }
        ),
    )
    sessions.add_draft_version(
        session_id,
        analysis_id=session_id,
        status="COMPLETED",
        content="## ADR: API Gateway Pattern\n\n[ASSUMPTION 1] On-premise is required.",
        assumptions_count=1,
        questions_count=0,
        risks_count=0,
    )


class TestSendChatMessageHandler:
    def test_replies_and_persists_both_messages(self, fake_llm, sessions):
        _seed_completed_session(sessions)
        fake_llm.response = "The gateway must stay on-premise per the constraint."
        handler = SendChatMessageHandler(fake_llm, SYSTEM_PROMPT, sessions)

        reply = handler.handle(SendChatMessageCommand(session_id="ADA-001", message="Why Kong over AWS?"))

        assert reply.role == "assistant"
        assert reply.content == "The gateway must stay on-premise per the constraint."
        session = sessions.get_session("ADA-001")
        assert [(m.role, m.content) for m in session.messages] == [
            ("user", "Why Kong over AWS?"),
            ("assistant", "The gateway must stay on-premise per the constraint."),
        ]

    def test_prompt_grounds_in_latest_draft_and_history(self, fake_llm, sessions):
        _seed_completed_session(sessions)
        sessions.add_message("ADA-001", "user", "earlier question")
        sessions.add_message("ADA-001", "assistant", "earlier answer")
        fake_llm.response = "ack"
        handler = SendChatMessageHandler(fake_llm, SYSTEM_PROMPT, sessions)

        handler.handle(SendChatMessageCommand(session_id="ADA-001", message="Why Kong over AWS?"))

        _, user_prompt = fake_llm.calls[0]
        assert "API Gateway Pattern" in user_prompt  # from the latest draft content
        assert "earlier question" in user_prompt
        assert "earlier answer" in user_prompt
        assert "Why Kong over AWS?" in user_prompt

    def test_reasoning_flows_from_gateway_into_the_persisted_reply(self, fake_llm, sessions):
        _seed_completed_session(sessions)
        fake_llm.response = "Stay on-premise."
        fake_llm.reasoning = "The constraint list rules out any managed/cloud option."
        handler = SendChatMessageHandler(fake_llm, SYSTEM_PROMPT, sessions)

        reply = handler.handle(SendChatMessageCommand(session_id="ADA-001", message="Why Kong?"))

        assert reply.reasoning == "The constraint list rules out any managed/cloud option."
        session = sessions.get_session("ADA-001")
        assert session.messages[-1].reasoning == "The constraint list rules out any managed/cloud option."
        assert session.messages[0].reasoning is None  # the user's own message never carries reasoning

    def test_unknown_session_raises_not_found(self, fake_llm, sessions):
        handler = SendChatMessageHandler(fake_llm, SYSTEM_PROMPT, sessions)

        with pytest.raises(SessionNotFoundError):
            handler.handle(SendChatMessageCommand(session_id="missing", message="hi"))

    def test_session_without_completed_draft_raises_unavailable(self, fake_llm, sessions):
        sessions.create_session(
            "ADA-BLOCKED", task_type="draft_adr", requirement_id=None, subject_ref="x", request_json="{}"
        )
        sessions.add_draft_version(
            "ADA-BLOCKED", analysis_id="ADA-BLOCKED", status="REJECTED", content="[REJECTED] secrets detected",
            assumptions_count=0, questions_count=0, risks_count=0,
        )
        handler = SendChatMessageHandler(fake_llm, SYSTEM_PROMPT, sessions)

        with pytest.raises(SessionDraftUnavailableError):
            handler.handle(SendChatMessageCommand(session_id="ADA-BLOCKED", message="hi"))
        assert fake_llm.calls == []


class TestRefineDraftHandler:
    def test_creates_next_draft_version_using_original_fields_and_conversation(self, fake_llm, event_bus, sessions):
        _seed_completed_session(sessions)
        sessions.add_message("ADA-001", "user", "Please prioritize on-premise support.")
        sessions.add_message("ADA-001", "assistant", "Noted — Kong fits that best.")
        fake_llm.response = "## ADR: API Gateway Pattern (v2)\n\nDecision: Kong."
        handler = RefineDraftHandler(fake_llm, SYSTEM_PROMPT, event_bus, sessions)

        analysis = handler.handle(RefineDraftCommand(session_id="ADA-001"))

        assert analysis.draft.content == "## ADR: API Gateway Pattern (v2)\n\nDecision: Kong."
        session = sessions.get_session("ADA-001")
        assert [v.version_no for v in session.versions] == [1, 2]
        assert session.latest_version.content == "## ADR: API Gateway Pattern (v2)\n\nDecision: Kong."

        _, user_prompt = fake_llm.calls[0]
        assert "Kong" in user_prompt  # original options_to_evaluate carried through
        assert "On-premise deployment required" in user_prompt  # original constraints carried through
        assert "Please prioritize on-premise support." in user_prompt  # chat folded in

    def test_reasoning_flows_into_the_new_draft_version(self, fake_llm, event_bus, sessions):
        _seed_completed_session(sessions)
        fake_llm.response = "## ADR: API Gateway Pattern (v2)"
        fake_llm.reasoning = "The SA's follow-up narrows it to the on-premise-capable options."
        handler = RefineDraftHandler(fake_llm, SYSTEM_PROMPT, event_bus, sessions)

        handler.handle(RefineDraftCommand(session_id="ADA-001"))

        session = sessions.get_session("ADA-001")
        assert session.latest_version.reasoning == "The SA's follow-up narrows it to the on-premise-capable options."

    def test_unknown_session_raises_not_found(self, fake_llm, event_bus, sessions):
        handler = RefineDraftHandler(fake_llm, SYSTEM_PROMPT, event_bus, sessions)

        with pytest.raises(SessionNotFoundError):
            handler.handle(RefineDraftCommand(session_id="missing"))

    def test_session_without_completed_draft_raises_unavailable(self, fake_llm, event_bus, sessions):
        sessions.create_session(
            "ADA-BLOCKED", task_type="draft_adr", requirement_id=None, subject_ref="x", request_json="{}"
        )
        sessions.add_draft_version(
            "ADA-BLOCKED", analysis_id="ADA-BLOCKED", status="BLOCKED", content="[BLOCKED] missing context",
            assumptions_count=0, questions_count=0, risks_count=0,
        )
        handler = RefineDraftHandler(fake_llm, SYSTEM_PROMPT, event_bus, sessions)

        with pytest.raises(SessionDraftUnavailableError):
            handler.handle(RefineDraftCommand(session_id="ADA-BLOCKED"))
        assert fake_llm.calls == []
