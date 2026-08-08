"""Command: input to the RequestImpactAnalysis use case (AIA's only slice)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RequestImpactAnalysisCommand:
    change_request_id: str
    change_request_text: str
    # Upstream REQ-ID this CR traces back to (Phase 1 — see spec/traceability.md).
    # Optional: not every caller has one; never fabricated if absent.
    requirement_id: Optional[str] = None
