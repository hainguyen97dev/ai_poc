"""Tests for AnalyzeRequirementHandler — ADA's requirement -> options slice."""

from __future__ import annotations

from domain.aggregates import AnalysisStatus
from features.analyze_requirement.command import AnalyzeRequirementCommand
from features.analyze_requirement.handler import AnalyzeRequirementHandler

SYSTEM_PROMPT = "You are the Architecture Decision Assistant."

SAMPLE_DRAFT = """## Architecture Options

Option A: ...

[ASSUMPTION 1] Team has Java/Spring Boot expertise.
[QUESTION 1] What's the target SLA for payments?
"""


def _handler(fake_llm, event_bus) -> AnalyzeRequirementHandler:
    return AnalyzeRequirementHandler(llm=fake_llm, system_prompt=SYSTEM_PROMPT, event_bus=event_bus)


class TestNormalPath:
    def test_completes_with_full_context(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        analysis = _handler(fake_llm, event_bus).handle(
            AnalyzeRequirementCommand(
                requirement_id="REQ-001",
                requirement_doc="# Integrate Payment Gateway",
                tech_stack=["Java", "Spring Boot"],
            )
        )

        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.draft.assumptions_count == 1
        assert analysis.draft.questions_count == 1

    def test_reasoning_flows_from_gateway_into_draft(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        fake_llm.reasoning = "Considered Java/Spring Boot fit before picking an option."

        analysis = _handler(fake_llm, event_bus).handle(
            AnalyzeRequirementCommand(requirement_id="REQ-001", requirement_doc="# Integrate Payment Gateway")
        )

        assert analysis.draft.reasoning == "Considered Java/Spring Boot fit before picking an option."

    def test_reasoning_is_none_when_gateway_does_not_provide_one(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT  # fake_llm.reasoning defaults to None

        analysis = _handler(fake_llm, event_bus).handle(
            AnalyzeRequirementCommand(requirement_id="REQ-001", requirement_doc="# Integrate Payment Gateway")
        )

        assert analysis.draft.reasoning is None


class TestMissingContextDoesNotBlock:
    """test_case_2 in the old fixtures: agent should ask clarifying questions,
    not refuse outright — analyze_requirement never blocks on empty context."""

    def test_still_completes_with_empty_context(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        analysis = _handler(fake_llm, event_bus).handle(
            AnalyzeRequirementCommand(requirement_id="REQ-002", requirement_doc="# Some requirement")
        )

        assert analysis.status == AnalysisStatus.COMPLETED
        assert len(fake_llm.calls) == 1

    def test_still_completes_with_no_requirement_doc(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        analysis = _handler(fake_llm, event_bus).handle(
            AnalyzeRequirementCommand(requirement_id="REQ-003", requirement_doc=None)
        )

        assert analysis.status == AnalysisStatus.COMPLETED
        _, user_prompt = fake_llm.calls[0]
        assert "[No requirement document provided]" in user_prompt


class TestSecretsInInput:
    def test_rejects_without_calling_the_llm(self, fake_llm, event_bus):
        analysis = _handler(fake_llm, event_bus).handle(
            AnalyzeRequirementCommand(
                requirement_id="REQ-CREDS",
                requirement_doc="VNPT API Key: sk_live_example, integrate payment gateway",
            )
        )

        assert analysis.status == AnalysisStatus.REJECTED
        assert fake_llm.calls == []
