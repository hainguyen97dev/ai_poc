"""Value Objects — self-validating, immutable data for the Architecture Change Analysis domain.

See spec/domain-model.md § Value Objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class DomainError(Exception):
    """Raised when a value object or aggregate invariant is violated."""


@dataclass(frozen=True)
class AnalysisId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise DomainError("AnalysisId cannot be empty")


@dataclass(frozen=True)
class ChangeRequestRef:
    """The thing being analyzed: a Change Request (AIA) or a requirement/decision context (ADA)."""

    id: str
    text: str
    version: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise DomainError("ChangeRequestRef must have non-empty text")


class RecommendationStatus(str, Enum):
    PROCEED = "PROCEED"
    PROCEED_WITH_CAUTION = "PROCEED_WITH_CAUTION"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class Draft:
    """The agent's output. Always unapproved — the contract never lets this look final.

    See agent-contract.md § 6 (Required Output Format): every response must be
    marked 'DRAFT — Pending Solution Architect Review'.
    """

    content: str
    recommendation: Optional[RecommendationStatus] = None
    assumptions_count: int = 0
    questions_count: int = 0
    risks_count: int = 0

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise DomainError("Draft content cannot be empty")


@dataclass(frozen=True)
class ValidationOutcome:
    """Result of the deterministic, pre-LLM input checks (domain/validation.py)."""

    rejected_reason: Optional[str] = None
    blocked_reason: Optional[str] = None
    injection_details: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_rejected(self) -> bool:
        return self.rejected_reason is not None

    @property
    def is_blocked(self) -> bool:
        return self.blocked_reason is not None

    @property
    def is_clean(self) -> bool:
        return not self.is_rejected and not self.is_blocked
