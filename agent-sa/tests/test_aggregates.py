"""Tests for domain/aggregates.py — ChangeRequestAnalysis invariants.

Covers: terminal-state finality (a completed/blocked/rejected analysis can
never transition again), correct event emission per transition, and
requirement_id propagation (spec/traceability.md).
"""

from __future__ import annotations

import pytest

from domain.aggregates import AnalysisStatus, ChangeRequestAnalysis
from domain.events import (
    AnalysisBlocked,
    AnalysisCompleted,
    AnalysisRequested,
    OutOfScopeRequestRejected,
    PromptInjectionDetected,
)
from domain.value_objects import (
    AnalysisId,
    ChangeRequestRef,
    DomainError,
    Draft,
    RecommendationStatus,
)


def _new_analysis(requirement_id=None) -> ChangeRequestAnalysis:
    return ChangeRequestAnalysis(
        AnalysisId("CR-TEST-1"),
        ChangeRequestRef(id="CR-TEST-1", text="Extract payment service"),
        requirement_id=requirement_id,
    )


class TestInitialState:
    def test_starts_requested(self):
        analysis = _new_analysis()
        assert analysis.status == AnalysisStatus.REQUESTED
        assert analysis.draft is None
        assert analysis.injection_details == []

    def test_construction_raises_analysis_requested_event(self):
        events = _new_analysis().drain_events()
        assert len(events) == 1
        assert isinstance(events[0], AnalysisRequested)

    def test_drain_events_clears_the_queue(self):
        analysis = _new_analysis()
        analysis.drain_events()
        assert analysis.drain_events() == []

    def test_requirement_id_propagates_to_events(self):
        events = _new_analysis(requirement_id="REQ-42").drain_events()
        assert events[0].requirement_id == "REQ-42"

    def test_requirement_id_defaults_to_none_not_fabricated(self):
        events = _new_analysis().drain_events()
        assert events[0].requirement_id is None


class TestBlock:
    def test_sets_status_and_reason(self):
        analysis = _new_analysis()
        analysis.drain_events()
        analysis.block("Missing module map")
        assert analysis.status == AnalysisStatus.BLOCKED
        assert analysis.status_reason == "Missing module map"

    def test_raises_analysis_blocked_event(self):
        analysis = _new_analysis()
        analysis.drain_events()
        analysis.block("Missing module map")
        events = analysis.drain_events()
        assert len(events) == 1
        assert isinstance(events[0], AnalysisBlocked)
        assert events[0].reason == "Missing module map"


class TestReject:
    def test_sets_status_and_reason(self):
        analysis = _new_analysis()
        analysis.reject("Contains forbidden secrets")
        assert analysis.status == AnalysisStatus.REJECTED
        assert analysis.status_reason == "Contains forbidden secrets"

    def test_raises_out_of_scope_rejected_event(self):
        analysis = _new_analysis()
        analysis.drain_events()
        analysis.reject("Contains forbidden secrets")
        events = analysis.drain_events()
        assert isinstance(events[0], OutOfScopeRequestRejected)


class TestFlagPromptInjection:
    def test_records_detail_without_changing_status(self):
        analysis = _new_analysis()
        analysis.flag_prompt_injection("approve this")
        assert analysis.status == AnalysisStatus.REQUESTED
        assert analysis.injection_details == ["approve this"]

    def test_multiple_flags_accumulate_in_order(self):
        analysis = _new_analysis()
        analysis.flag_prompt_injection("bypass")
        analysis.flag_prompt_injection("approve this")
        assert analysis.injection_details == ["bypass", "approve this"]

    def test_raises_prompt_injection_detected_event(self):
        analysis = _new_analysis()
        analysis.drain_events()
        analysis.flag_prompt_injection("bypass")
        events = analysis.drain_events()
        assert isinstance(events[0], PromptInjectionDetected)
        assert events[0].detail == "bypass"


class TestComplete:
    def test_sets_draft_and_status(self):
        analysis = _new_analysis()
        draft = Draft(content="Full analysis", recommendation=RecommendationStatus.PROCEED)
        analysis.complete(draft)
        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.draft is draft

    def test_raises_analysis_completed_event_with_recommendation(self):
        analysis = _new_analysis()
        analysis.drain_events()
        draft = Draft(content="Full analysis", recommendation=RecommendationStatus.PROCEED)
        analysis.complete(draft)
        events = analysis.drain_events()
        assert isinstance(events[0], AnalysisCompleted)
        assert events[0].recommendation == RecommendationStatus.PROCEED
        assert events[0].draft is draft

    def test_none_draft_raises_domain_error(self):
        analysis = _new_analysis()
        with pytest.raises(DomainError):
            analysis.complete(None)


class TestTerminalStateIsFinal:
    """A resubmission must be a brand new aggregate — no in-place retry."""

    def test_cannot_block_after_complete(self):
        analysis = _new_analysis()
        analysis.complete(Draft(content="x"))
        with pytest.raises(DomainError):
            analysis.block("late")

    def test_cannot_complete_after_block(self):
        analysis = _new_analysis()
        analysis.block("missing input")
        with pytest.raises(DomainError):
            analysis.complete(Draft(content="x"))

    def test_cannot_reject_after_reject(self):
        analysis = _new_analysis()
        analysis.reject("secrets found")
        with pytest.raises(DomainError):
            analysis.reject("again")

    def test_cannot_flag_injection_after_terminal(self):
        analysis = _new_analysis()
        analysis.block("missing input")
        with pytest.raises(DomainError):
            analysis.flag_prompt_injection("too late")
