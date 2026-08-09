"""Handler for AnalyzeRequirement — ADA's requirement -> architecture-options slice."""

from __future__ import annotations

import uuid

from domain.aggregates import ChangeRequestAnalysis
from domain.ports import LlmGateway
from domain.validation import validate_input
from domain.value_objects import AnalysisId, ChangeRequestRef, Draft
from infra.event_bus import EventBus

from .command import AnalyzeRequirementCommand


def build_prompt(cmd: AnalyzeRequirementCommand) -> str:
    context_parts = []
    if cmd.as_is_architecture:
        context_parts.append(f"**Current Architecture:**\n{cmd.as_is_architecture}")
    if cmd.tech_stack:
        context_parts.append(f"**Tech Stack:** {', '.join(cmd.tech_stack)}")
    if cmd.constraints:
        context_parts.append("**Constraints:**\n- " + "\n- ".join(cmd.constraints))
    if cmd.known_issues:
        context_parts.append("**Known Issues:**\n- " + "\n- ".join(cmd.known_issues))
    if cmd.conversation_context:
        context_parts.append(cmd.conversation_context)
    context_str = "\n\n".join(context_parts) or "[No context provided]"

    return f"""
TASK: Analyze Requirement and Generate Architecture Options

REQUEST ID: {cmd.requirement_id or "REQ-AUTO"}

REQUIREMENT DOCUMENT:
{cmd.requirement_doc or "[No requirement document provided]"}

CONTEXT:
{context_str}

Please analyze this requirement and produce:
1. 2-3 viable architecture options with trade-offs
2. Non-Functional Requirements checklist
3. Gap & Impact Analysis
4. ADR draft
5. Assumptions and open questions
6. Risks with mitigations

Follow the output format exactly as specified in your system instructions.
"""


class AnalyzeRequirementHandler:
    def __init__(self, llm: LlmGateway, system_prompt: str, event_bus: EventBus):
        self._llm = llm
        self._system_prompt = system_prompt
        self._event_bus = event_bus

    def handle(self, cmd: AnalyzeRequirementCommand) -> ChangeRequestAnalysis:
        analysis_id = AnalysisId(cmd.requirement_id or f"ADA-{uuid.uuid4().hex[:8]}")
        subject_text = cmd.requirement_doc or "[No requirement document provided]"
        # requirement_id doubles as this slice's own id and the upstream REQ-ID
        # (spec/traceability.md) — the requirement *is* the direct input here.
        analysis = ChangeRequestAnalysis(
            analysis_id,
            ChangeRequestRef(id=analysis_id.value, text=subject_text),
            requirement_id=cmd.requirement_id,
        )

        # ADA doesn't block on missing context (test_case_2: "should ask clarifying
        # questions", "should_not_contain: Cannot proceed") — only secrets are fatal.
        outcome = validate_input(subject_text, require_module_map=False)

        if outcome.is_rejected:
            analysis.reject(outcome.rejected_reason)
        else:
            for detail in outcome.injection_details:
                analysis.flag_prompt_injection(detail)

            result = self._llm.generate_with_reasoning(self._system_prompt, build_prompt(cmd))
            draft_text = result.content
            draft = Draft(
                content=draft_text,
                reasoning=result.reasoning,
                assumptions_count=draft_text.count("[ASSUMPTION"),
                questions_count=draft_text.count("[QUESTION"),
                risks_count=max(0, draft_text.lower().count("| risk") - 1),
            )
            analysis.complete(draft)

        self._event_bus.publish_all(analysis.drain_events())
        return analysis
