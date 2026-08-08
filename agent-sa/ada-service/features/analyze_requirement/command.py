"""Command: input to the AnalyzeRequirement use case (ADA)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class AnalyzeRequirementCommand:
    requirement_id: str
    requirement_doc: Optional[str]
    as_is_architecture: Optional[str] = None
    tech_stack: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    known_issues: List[str] = field(default_factory=list)
