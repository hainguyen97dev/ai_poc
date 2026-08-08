"""Handler for RunGapImpactAnalysis — ADA's change-request -> gap/impact slice."""

from __future__ import annotations

import uuid

from domain.aggregates import ChangeRequestAnalysis
from domain.ports import LlmGateway
from domain.validation import validate_input
from domain.value_objects import AnalysisId, ChangeRequestRef, Draft
from infra.event_bus import EventBus

from .command import RunGapImpactAnalysisCommand


def build_prompt(cmd: RunGapImpactAnalysisCommand) -> str:
    context_parts = []
    if cmd.affected_modules:
        context_parts.append(f"**Affected Modules:** {', '.join(cmd.affected_modules)}")
    if cmd.current_design_doc:
        context_parts.append(f"**Current Design:**\n{cmd.current_design_doc}")
    context_str = "\n\n".join(context_parts) or "[No context provided]"

    return f"""
TASK: Gap & Impact Analysis

CHANGE REQUEST ID: {cmd.change_request_id or "CR-AUTO"}

CHANGE DESCRIPTION:
{cmd.change_description or "[No change description provided]"}

CONTEXT:
{context_str}

Please produce:
1. Detailed Gap & Impact Analysis table
2. Affected modules and components
3. Risks and mitigation strategies
4. Assumptions and open questions
5. Recommendations for implementation

Follow the output format exactly as specified in your system instructions.
"""


class RunGapImpactAnalysisHandler:
    def __init__(self, llm: LlmGateway, system_prompt: str, event_bus: EventBus):
        self._llm = llm
        self._system_prompt = system_prompt
        self._event_bus = event_bus

    def handle(self, cmd: RunGapImpactAnalysisCommand) -> ChangeRequestAnalysis:
        analysis_id = AnalysisId(cmd.change_request_id or f"ADA-{uuid.uuid4().hex[:8]}")
        subject_text = cmd.change_description or "[No change description provided]"
        analysis = ChangeRequestAnalysis(analysis_id, ChangeRequestRef(id=analysis_id.value, text=subject_text))

        outcome = validate_input(subject_text, require_module_map=False)

        if outcome.is_rejected:
            analysis.reject(outcome.rejected_reason)
        else:
            for detail in outcome.injection_details:
                analysis.flag_prompt_injection(detail)

            draft_text = self._llm.generate(self._system_prompt, build_prompt(cmd))
            draft = Draft(
                content=draft_text,
                assumptions_count=draft_text.count("[ASSUMPTION"),
                questions_count=draft_text.count("[QUESTION"),
                risks_count=max(0, draft_text.lower().count("| risk") - 1),
            )
            analysis.complete(draft)

        self._event_bus.publish_all(analysis.drain_events())
        return analysis
