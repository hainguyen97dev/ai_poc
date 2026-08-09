"""Command: input to the DraftAdr use case (ADA)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class DraftAdrCommand:
    decision_title: Optional[str]
    options_to_evaluate: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    current_architecture: Optional[str] = None
    # Upstream REQ-ID this decision traces back to (Phase 1 — see spec/traceability.md).
    requirement_id: Optional[str] = None
    # Chat transcript since the last draft version, folded in by
    # features/chat_session/refine_draft_handler.py on "Refine draft". None
    # for a normal /api/v1/analyze call.
    conversation_context: Optional[str] = None
