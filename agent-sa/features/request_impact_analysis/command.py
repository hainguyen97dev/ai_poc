"""Command: input to the RequestImpactAnalysis use case (AIA's only slice)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestImpactAnalysisCommand:
    change_request_id: str
    change_request_text: str
