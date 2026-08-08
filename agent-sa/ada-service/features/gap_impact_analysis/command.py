"""Command: input to the RunGapImpactAnalysis use case (ADA)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class RunGapImpactAnalysisCommand:
    change_request_id: str
    change_description: Optional[str]
    affected_modules: List[str] = field(default_factory=list)
    current_design_doc: Optional[str] = None
