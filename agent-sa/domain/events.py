"""Domain Events — facts about what happened, past tense.

Aggregates raise these; handlers publish them to infra.event_bus.EventBus;
infra listeners react to them (audit logging, writing output files, ...).
Handlers never do I/O directly — see spec/domain-model.md § Event Flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .value_objects import AnalysisId, Draft, RecommendationStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DomainEvent:
    analysis_id: AnalysisId
    occurred_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class AnalysisRequested(DomainEvent):
    subject_summary: str = ""


@dataclass(frozen=True)
class AnalysisBlocked(DomainEvent):
    reason: str = ""


@dataclass(frozen=True)
class OutOfScopeRequestRejected(DomainEvent):
    reason: str = ""


@dataclass(frozen=True)
class PromptInjectionDetected(DomainEvent):
    detail: str = ""


@dataclass(frozen=True)
class AnalysisCompleted(DomainEvent):
    draft: Optional[Draft] = None
    recommendation: Optional[RecommendationStatus] = None
