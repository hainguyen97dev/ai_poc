"""Handler for RequestImpactAnalysis — the one command AIA has.

Its five CLI test scenarios (normal / incomplete / out_of_scope /
prompt_injection / missing_source) are the same use case exercised with
different inputs, not different use cases: domain.validation.validate_input()
decides which event comes out — the caller never picks a branch.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Optional

from domain.aggregates import ChangeRequestAnalysis
from domain.ports import LlmGateway
from domain.validation import validate_input
from domain.value_objects import AnalysisId, ChangeRequestRef, Draft, RecommendationStatus
from infra.event_bus import EventBus

from .command import RequestImpactAnalysisCommand

USER_PROMPT_TEMPLATE = """ANALYZE THIS CHANGE REQUEST AND PRODUCE IMPACT ANALYSIS

{cr_text}

Remember to follow the output format from your system instructions exactly.
"""

_STATUS_RE = re.compile(
    r"\*\*Status:\*\*\s*`?(PROCEED_WITH_CAUTION|PROCEED|ESCALATE)`?", re.IGNORECASE
)


def build_user_prompt(change_request_text: str) -> str:
    """Exposed separately so the CLI's --dry-run path can render the exact
    prompt without going through the handler (no aggregate, no LLM call)."""
    return USER_PROMPT_TEMPLATE.format(cr_text=change_request_text)


@dataclass
class RequestImpactAnalysisResult:
    """What the CLI adapter renders — the aggregate's outcome, nothing more."""

    analysis: ChangeRequestAnalysis


class RequestImpactAnalysisHandler:
    def __init__(self, llm: LlmGateway, system_prompt: str, event_bus: EventBus):
        self._llm = llm
        self._system_prompt = system_prompt
        self._event_bus = event_bus

    def handle(self, command: RequestImpactAnalysisCommand) -> RequestImpactAnalysisResult:
        analysis_id = AnalysisId(command.change_request_id or f"AIA-{uuid.uuid4().hex[:8]}")
        subject = ChangeRequestRef(id=analysis_id.value, text=command.change_request_text)
        analysis = ChangeRequestAnalysis(analysis_id, subject)

        outcome = validate_input(command.change_request_text)

        if outcome.is_rejected:
            analysis.reject(outcome.rejected_reason)
        elif outcome.is_blocked:
            analysis.block(outcome.blocked_reason)
        else:
            for detail in outcome.injection_details:
                analysis.flag_prompt_injection(detail)

            user_prompt = build_user_prompt(command.change_request_text)
            draft_text = self._llm.generate(self._system_prompt, user_prompt)
            draft = Draft(
                content=draft_text,
                recommendation=_extract_recommendation(draft_text),
                assumptions_count=draft_text.count("[ASSUMPTION"),
                questions_count=draft_text.count("[QUESTION"),
                risks_count=max(0, draft_text.lower().count("| risk") - 1),
            )
            analysis.complete(draft)

        self._event_bus.publish_all(analysis.drain_events())
        return RequestImpactAnalysisResult(analysis=analysis)


def _extract_recommendation(text: str) -> Optional[RecommendationStatus]:
    match = _STATUS_RE.search(text)
    if not match:
        return None
    return RecommendationStatus(match.group(1).upper())
