"""Aggregates — enforce invariants for the Architecture Change Analysis domain.

See spec/domain-model.md § Aggregates.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from .events import (
    AnalysisBlocked,
    AnalysisCompleted,
    AnalysisRequested,
    DomainEvent,
    OutOfScopeRequestRejected,
    PromptInjectionDetected,
)
from .value_objects import AnalysisId, ChangeRequestRef, Draft, DomainError


class AnalysisStatus(str, Enum):
    REQUESTED = "REQUESTED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class ChangeRequestAnalysis:
    """Aggregate root: one analysis run, from request to draft (or escalation).

    A terminal status (BLOCKED / REJECTED / COMPLETED) is final — there is no
    in-place retry. A resubmission is a brand new aggregate instance, which is
    also what agent-contract.md's escalation flow expects ("Resubmit with
    complete inputs").
    """

    def __init__(
        self,
        analysis_id: AnalysisId,
        subject: ChangeRequestRef,
        requirement_id: Optional[str] = None,
    ):
        self.id = analysis_id
        self.subject = subject
        # Upstream requirement this analysis traces back to (Phase 1, BA/PO —
        # see spec/traceability.md). Optional: not every CR has one on hand,
        # and this agent never invents one.
        self.requirement_id = requirement_id
        self.status = AnalysisStatus.REQUESTED
        self.draft: Optional[Draft] = None
        # Convenience mirrors of the last-raised event's payload, so adapters
        # (CLI stdout, HTTP responses) can render a result *after* events have
        # already been drained and published — they don't need to re-read events.
        self.status_reason: Optional[str] = None
        self.injection_details: List[str] = []
        self._events: List[DomainEvent] = [
            AnalysisRequested(
                analysis_id, requirement_id=requirement_id, subject_summary=subject.text[:80]
            )
        ]

    def flag_prompt_injection(self, detail: str) -> None:
        """Non-blocking: records that embedded instructions were detected.

        Does not change status — analysis still proceeds to completion,
        matching system-instructions.md § IV.6: "Proceeding with standard
        analysis anyway" / "Flag the manipulation attempt".
        """
        self._guard_mutable()
        self.injection_details.append(detail)
        self._events.append(
            PromptInjectionDetected(self.id, requirement_id=self.requirement_id, detail=detail)
        )

    def block(self, reason: str) -> None:
        self._guard_mutable()
        self.status = AnalysisStatus.BLOCKED
        self.status_reason = reason
        self._events.append(
            AnalysisBlocked(self.id, requirement_id=self.requirement_id, reason=reason)
        )

    def reject(self, reason: str) -> None:
        self._guard_mutable()
        self.status = AnalysisStatus.REJECTED
        self.status_reason = reason
        self._events.append(
            OutOfScopeRequestRejected(self.id, requirement_id=self.requirement_id, reason=reason)
        )

    def complete(self, draft: Draft) -> None:
        self._guard_mutable()
        if draft is None:
            raise DomainError("Cannot complete an analysis without a Draft")
        self.status = AnalysisStatus.COMPLETED
        self.draft = draft
        self._events.append(
            AnalysisCompleted(
                self.id,
                requirement_id=self.requirement_id,
                draft=draft,
                recommendation=draft.recommendation,
            )
        )

    def drain_events(self) -> List[DomainEvent]:
        """Return and clear pending events (call once, right before publishing)."""
        events, self._events = self._events, []
        return events

    def _guard_mutable(self) -> None:
        if self.status != AnalysisStatus.REQUESTED:
            raise DomainError(
                f"Analysis {self.id.value} is already {self.status.value}; "
                "cannot transition again — start a new analysis instead"
            )
