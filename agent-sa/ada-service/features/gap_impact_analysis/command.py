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
    # Upstream REQ-ID this CR traces back to (Phase 1 — see spec/traceability.md).
    requirement_id: Optional[str] = None
    # Chat transcript since the last draft version, folded in by
    # features/chat_session/refine_draft_handler.py on "Refine draft". None
    # for a normal /api/v1/analyze call.
    conversation_context: Optional[str] = None
