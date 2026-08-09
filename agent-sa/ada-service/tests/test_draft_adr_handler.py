"""Tests for DraftAdrHandler — ADA's decision -> ADR-draft slice."""

from __future__ import annotations

from domain.aggregates import AnalysisStatus
from features.draft_adr.command import DraftAdrCommand
from features.draft_adr.handler import DraftAdrHandler

SYSTEM_PROMPT = "You are the Architecture Decision Assistant."

SAMPLE_DRAFT = """## ADR: API Gateway Pattern

**Decision:** Use Kong.

[ASSUMPTION 1] On-premise deployment is a hard constraint.
"""


def _handler(fake_llm, event_bus) -> DraftAdrHandler:
    return DraftAdrHandler(llm=fake_llm, system_prompt=SYSTEM_PROMPT, event_bus=event_bus)


class TestNormalPath:
    def test_completes_and_derives_id_from_title(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        analysis = _handler(fake_llm, event_bus).handle(
            DraftAdrCommand(
                decision_title="API Gateway Pattern for VNPT Integration",
                options_to_evaluate=["Kong", "AWS API Gateway"],
                constraints=["On-premise deployment required"],
            )
        )

        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.id.value.startswith("ADR-API-GATEWAY-PATTERN")
        assert analysis.draft.assumptions_count == 1

    def test_prompt_includes_options_and_constraints(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        _handler(fake_llm, event_bus).handle(
            DraftAdrCommand(
                decision_title="API Gateway Pattern",
                options_to_evaluate=["Kong", "AWS API Gateway"],
                constraints=["On-premise deployment required"],
            )
        )

        _, user_prompt = fake_llm.calls[0]
        assert "Kong" in user_prompt
        assert "On-premise deployment required" in user_prompt

    def test_reasoning_flows_from_gateway_into_draft(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        fake_llm.reasoning = "Kong fits the on-premise constraint; AWS API Gateway doesn't."
        analysis = _handler(fake_llm, event_bus).handle(
            DraftAdrCommand(decision_title="API Gateway Pattern", options_to_evaluate=["Kong"])
        )

        assert analysis.draft.reasoning == "Kong fits the on-premise constraint; AWS API Gateway doesn't."

    def test_prompt_includes_current_architecture_baseline(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        _handler(fake_llm, event_bus).handle(
            DraftAdrCommand(
                decision_title="API Gateway Pattern",
                current_architecture="Current system uses a Spring Boot monolith.",
            )
        )

        _, user_prompt = fake_llm.calls[0]
        assert "Current Architecture Baseline" in user_prompt
        assert "Spring Boot monolith" in user_prompt


class TestNoDecisionTitle:
    def test_falls_back_to_generated_id(self, fake_llm, event_bus):
        fake_llm.response = SAMPLE_DRAFT
        analysis = _handler(fake_llm, event_bus).handle(DraftAdrCommand(decision_title=None))

        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.id.value.startswith("ADR-")


class TestSecretsInInput:
    def test_rejects_without_calling_the_llm(self, fake_llm, event_bus):
        analysis = _handler(fake_llm, event_bus).handle(
            DraftAdrCommand(decision_title="Use password: hunter2 as the gateway secret")
        )

        assert analysis.status == AnalysisStatus.REJECTED
        assert fake_llm.calls == []
