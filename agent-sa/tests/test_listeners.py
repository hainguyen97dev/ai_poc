"""Tests for infra/listeners.py — the side effects triggered by domain events."""

from __future__ import annotations

from domain.events import (
    AnalysisBlocked,
    AnalysisCompleted,
    OutOfScopeRequestRejected,
    PromptInjectionDetected,
)
from domain.value_objects import AnalysisId, Draft, RecommendationStatus
from infra.listeners import AuditLogListener, OutputWriterListener


class TestAuditLogListener:
    def test_on_completed_logs_requirement_id_and_recommendation(self, tmp_path):
        log_file = tmp_path / "AI_USAGE_LOG.md"
        listener = AuditLogListener(log_file)

        listener.on_completed(
            AnalysisCompleted(
                AnalysisId("CR-1"),
                requirement_id="REQ-1",
                draft=Draft(content="x"),
                recommendation=RecommendationStatus.PROCEED,
            )
        )

        line = log_file.read_text(encoding="utf-8").strip()
        assert "req=REQ-1" in line
        assert "CR-1" in line
        assert "COMPLETED" in line
        assert "recommendation=PROCEED" in line

    def test_on_completed_with_no_requirement_id_logs_tbd_not_fabricated(self, tmp_path):
        log_file = tmp_path / "AI_USAGE_LOG.md"
        listener = AuditLogListener(log_file)

        listener.on_completed(
            AnalysisCompleted(AnalysisId("CR-2"), draft=Draft(content="x"), recommendation=None)
        )

        line = log_file.read_text(encoding="utf-8").strip()
        assert "req=TBD" in line
        assert "recommendation=UNSPECIFIED" in line

    def test_on_blocked_logs_reason(self, tmp_path):
        log_file = tmp_path / "AI_USAGE_LOG.md"
        listener = AuditLogListener(log_file)

        listener.on_blocked(AnalysisBlocked(AnalysisId("CR-3"), reason="Missing module map"))

        line = log_file.read_text(encoding="utf-8").strip()
        assert "BLOCKED" in line
        assert "reason=Missing module map" in line

    def test_on_rejected_logs_reason(self, tmp_path):
        log_file = tmp_path / "AI_USAGE_LOG.md"
        listener = AuditLogListener(log_file)

        listener.on_rejected(OutOfScopeRequestRejected(AnalysisId("CR-4"), reason="secret detected"))

        line = log_file.read_text(encoding="utf-8").strip()
        assert "REJECTED" in line
        assert "reason=secret detected" in line

    def test_on_injection_detected_logs_detail(self, tmp_path):
        log_file = tmp_path / "AI_USAGE_LOG.md"
        listener = AuditLogListener(log_file)

        listener.on_injection_detected(PromptInjectionDetected(AnalysisId("CR-5"), detail="approve this"))

        line = log_file.read_text(encoding="utf-8").strip()
        assert "INJECTION_DETECTED" in line
        assert "detail=approve this" in line

    def test_appends_multiple_events_as_separate_lines(self, tmp_path):
        log_file = tmp_path / "AI_USAGE_LOG.md"
        listener = AuditLogListener(log_file)

        listener.on_blocked(AnalysisBlocked(AnalysisId("A"), reason="r1"))
        listener.on_blocked(AnalysisBlocked(AnalysisId("B"), reason="r2"))

        assert len(log_file.read_text(encoding="utf-8").splitlines()) == 2

    def test_creates_parent_directories_if_missing(self, tmp_path):
        log_file = tmp_path / "nested" / "dir" / "log.md"
        listener = AuditLogListener(log_file)

        listener.on_rejected(OutOfScopeRequestRejected(AnalysisId("CR-6"), reason="x"))

        assert log_file.exists()


class TestOutputWriterListener:
    def test_writes_draft_content_to_run_named_file(self, tmp_path):
        listener = OutputWriterListener(tmp_path, "normal")

        listener.on_completed(
            AnalysisCompleted(AnalysisId("CR-1"), draft=Draft(content="## Analysis\ncontent"), recommendation=None)
        )

        output_file = tmp_path / "run-normal.md"
        assert output_file.read_text(encoding="utf-8") == "## Analysis\ncontent"

    def test_creates_outputs_dir_if_missing(self, tmp_path):
        outputs_dir = tmp_path / "outputs"
        listener = OutputWriterListener(outputs_dir, "incomplete")

        listener.on_completed(
            AnalysisCompleted(AnalysisId("CR-2"), draft=Draft(content="x"), recommendation=None)
        )

        assert (outputs_dir / "run-incomplete.md").exists()
