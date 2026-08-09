"""Handler for RefineDraft — regenerate a session's draft using its chat
history as extra context.

Reuses the *unchanged* task-type handlers (AnalyzeRequirementHandler,
RunGapImpactAnalysisHandler, DraftAdrHandler): each produces a brand-new
ChangeRequestAnalysis run, exactly as domain/aggregates.py already requires
("a resubmission is a brand new aggregate instance"). Only the Command's
`conversation_context` field (added for this feature) carries the chat
transcript in — no handler business logic changes.
See docs/superpowers/specs/2026-08-09-ada-chat-session-design.md.
"""

from __future__ import annotations

import json
from typing import Optional, Sequence

from domain.aggregates import ChangeRequestAnalysis
from domain.ports import LlmGateway, SessionRepository
from domain.session import ChatMessage
from infra.event_bus import EventBus

from features.analyze_requirement.command import AnalyzeRequirementCommand
from features.analyze_requirement.handler import AnalyzeRequirementHandler
from features.draft_adr.command import DraftAdrCommand
from features.draft_adr.handler import DraftAdrHandler
from features.gap_impact_analysis.command import RunGapImpactAnalysisCommand
from features.gap_impact_analysis.handler import RunGapImpactAnalysisHandler

from .command import RefineDraftCommand
from .errors import SessionDraftUnavailableError, SessionNotFoundError

_COMMAND_BY_TASK_TYPE = {
    "analyze_requirement": AnalyzeRequirementCommand,
    "gap_impact_analysis": RunGapImpactAnalysisCommand,
    "draft_adr": DraftAdrCommand,
}
_HANDLER_BY_TASK_TYPE = {
    "analyze_requirement": AnalyzeRequirementHandler,
    "gap_impact_analysis": RunGapImpactAnalysisHandler,
    "draft_adr": DraftAdrHandler,
}


def _format_conversation(messages: Sequence[ChatMessage]) -> Optional[str]:
    if not messages:
        return None
    lines = [f"{m.role.upper()}: {m.content}" for m in messages]
    return "**Conversation Since Last Draft:**\n" + "\n\n".join(lines)


class RefineDraftHandler:
    def __init__(
        self,
        llm: LlmGateway,
        system_prompt: str,
        event_bus: EventBus,
        sessions: SessionRepository,
    ):
        self._llm = llm
        self._system_prompt = system_prompt
        self._event_bus = event_bus
        self._sessions = sessions

    def handle(self, cmd: RefineDraftCommand) -> ChangeRequestAnalysis:
        session = self._sessions.get_session(cmd.session_id)
        if session is None:
            raise SessionNotFoundError(cmd.session_id)

        latest = session.latest_version
        if latest is None or latest.status != "COMPLETED":
            raise SessionDraftUnavailableError(
                cmd.session_id,
                f"Session '{cmd.session_id}' has no completed draft to refine "
                f"(latest status: {latest.status if latest else 'NONE'})",
            )

        command_cls = _COMMAND_BY_TASK_TYPE[session.task_type]
        handler_cls = _HANDLER_BY_TASK_TYPE[session.task_type]

        original_fields = json.loads(session.request_json)
        original_fields["conversation_context"] = _format_conversation(session.messages)
        refine_cmd = command_cls(**original_fields)

        handler = handler_cls(self._llm, self._system_prompt, self._event_bus)
        analysis = handler.handle(refine_cmd)

        draft = analysis.draft
        if draft is not None:
            self._sessions.add_draft_version(
                cmd.session_id,
                analysis_id=analysis.id.value,
                status=analysis.status.value,
                content=draft.content,
                reasoning=draft.reasoning,
                assumptions_count=draft.assumptions_count,
                questions_count=draft.questions_count,
                risks_count=draft.risks_count,
            )
        else:
            self._sessions.add_draft_version(
                cmd.session_id,
                analysis_id=analysis.id.value,
                status=analysis.status.value,
                content=f"[{analysis.status.value}] {analysis.status_reason or ''}".strip(),
                assumptions_count=0,
                questions_count=0,
                risks_count=0,
            )
        return analysis
