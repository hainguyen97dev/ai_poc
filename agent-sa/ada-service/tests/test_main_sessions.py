"""Regression test for the session-id collision bug: re-running /analyze with
the same human-supplied id (requirement_id / change_request_id / decision
slug) must never collide in the session store, since AnalysisId intentionally
reuses that id across independent runs (features/*/handler.py) — see
main.py's _persist_session docstring and docs/superpowers/specs/
2026-08-09-ada-chat-session-design.md.

Exercises the real FastAPI app end-to-end via TestClient, with a fake LLM
gateway and a temp-file SQLite session store — no real network calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from domain.ports import LlmResult
from infra.session_store import SqliteSessionRepository


class FakeLlmGateway:
    def __init__(self, reasoning=None):
        self.calls = []
        self.reasoning = reasoning

    def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return f"## Draft #{len(self.calls)}\n\n[ASSUMPTION 1] placeholder."

    def generate_with_reasoning(self, system_prompt, user_prompt):
        content = self.generate(system_prompt, user_prompt)
        return LlmResult(content=content, reasoning=self.reasoning)

    def is_available(self):
        return True


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "llm_gateway", FakeLlmGateway())
    monkeypatch.setattr(main, "session_repo", SqliteSessionRepository(tmp_path / "sessions.db"))
    # _build_event_bus() wires AuditLogListener(AI_USAGE_LOG) unconditionally —
    # redirect it to a temp file so this suite never appends synthetic runs to
    # the project's real agent-sa/AI_USAGE_LOG.md audit trail.
    monkeypatch.setattr(main, "AI_USAGE_LOG", tmp_path / "AI_USAGE_LOG.md")
    return TestClient(main.app)


def test_rerunning_same_requirement_id_creates_two_distinct_sessions(client):
    payload = {
        "task_type": "analyze_requirement",
        "requirement_id": "REQ-001",
        "requirement_doc": "Payment gateway v1",
    }

    first = client.post("/api/v1/analyze", json=payload)
    second = client.post("/api/v1/analyze", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text  # was a 500 (IntegrityError) before the fix

    first_body, second_body = first.json(), second.json()
    assert first_body["request_id"] == second_body["request_id"] == "REQ-001"
    assert first_body["session_id"] != second_body["session_id"]

    sessions = client.get("/api/v1/sessions").json()
    session_ids = {s["id"] for s in sessions}
    assert {first_body["session_id"], second_body["session_id"]} <= session_ids


def test_rerunning_same_decision_title_creates_two_distinct_sessions(client):
    payload = {"task_type": "draft_adr", "decision_title": "API Gateway Pattern"}

    first = client.post("/api/v1/analyze", json=payload)
    second = client.post("/api/v1/analyze", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["session_id"] != second.json()["session_id"]


def test_sample_inputs_include_a_static_preview_for_each_task_type(client):
    response = client.get("/api/v1/sample-inputs")

    assert response.status_code == 200
    samples = response.json()["samples"]
    for task_type in ("analyze_requirement", "gap_impact_analysis", "draft_adr"):
        preview = samples[task_type]["preview"]
        assert preview["analysis"]
        assert isinstance(preview["assumptions_count"], int)
        assert preview["chat"], f"{task_type} preview has no example chat turns"
        assert preview["chat"][0]["role"] == "user"
        assert preview["chat"][1]["role"] == "assistant"
        assert preview["chat"][1]["reasoning"]  # the example assistant turn shows reasoning off the bat


def test_analyze_response_session_id_opens_the_session_it_just_created(client):
    payload = {"task_type": "draft_adr", "decision_title": "Event Backbone"}

    response = client.post("/api/v1/analyze", json=payload)
    session_id = response.json()["session_id"]

    detail = client.get(f"/api/v1/sessions/{session_id}")

    assert detail.status_code == 200
    assert detail.json()["versions"][0]["content"] == response.json()["analysis"]


def test_usage_endpoint_reflects_analyze_refine_and_chat_calls(client):
    payload = {"task_type": "draft_adr", "decision_title": "Usage Test ADR"}
    analyze = client.post("/api/v1/analyze", json=payload)
    session_id = analyze.json()["session_id"]

    usage_after_analyze = client.get("/api/v1/usage").json()
    assert usage_after_analyze["by_kind"]["draft_adr"] == 1
    assert usage_after_analyze["by_kind"].get("chat_reply", 0) == 0
    assert usage_after_analyze["total"] == 1

    client.post(f"/api/v1/sessions/{session_id}/messages", json={"message": "why?"})
    client.post(f"/api/v1/sessions/{session_id}/refine")

    usage_after_all = client.get("/api/v1/usage").json()
    assert usage_after_all["by_kind"]["draft_adr"] == 2  # v1 + refine
    assert usage_after_all["by_kind"]["chat_reply"] == 1
    assert usage_after_all["total"] == 3


def test_analyze_response_and_persisted_version_both_carry_reasoning(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "llm_gateway", FakeLlmGateway(reasoning="On-premise rules out AWS API Gateway."))
    monkeypatch.setattr(main, "session_repo", SqliteSessionRepository(tmp_path / "sessions.db"))
    monkeypatch.setattr(main, "AI_USAGE_LOG", tmp_path / "AI_USAGE_LOG.md")
    client = TestClient(main.app)

    response = client.post("/api/v1/analyze", json={"task_type": "draft_adr", "decision_title": "API Gateway"})
    session_id = response.json()["session_id"]

    assert response.json()["reasoning"] == "On-premise rules out AWS API Gateway."
    detail = client.get(f"/api/v1/sessions/{session_id}").json()
    assert detail["versions"][0]["reasoning"] == "On-premise rules out AWS API Gateway."
