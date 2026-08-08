"""Handler for DraftAdr — ADA's decision -> ADR-draft slice."""

from __future__ import annotations

import re
import uuid

from domain.aggregates import ChangeRequestAnalysis
from domain.ports import LlmGateway
from domain.validation import validate_input
from domain.value_objects import AnalysisId, ChangeRequestRef, Draft
from infra.event_bus import EventBus

from .command import DraftAdrCommand


def build_prompt(cmd: DraftAdrCommand) -> str:
    context_parts = []
    if cmd.options_to_evaluate:
        context_parts.append("**Options to Evaluate:**\n- " + "\n- ".join(cmd.options_to_evaluate))
    if cmd.constraints:
        context_parts.append("**Constraints:**\n- " + "\n- ".join(cmd.constraints))
    context_str = "\n\n".join(context_parts) or "[No context provided]"

    return f"""
TASK: Draft Architecture Decision Record (ADR)

DECISION: {cmd.decision_title or "[No title provided]"}

CONTEXT:
{context_str}

Please produce a complete ADR draft with:
1. Context section (problem, drivers, constraints)
2. Decision statement and rationale
3. Alternatives considered
4. Consequences (benefits and trade-offs)
5. Implementation notes
6. Related decisions

Follow the output format exactly as specified in your system instructions.
"""


def _subject_text(cmd: DraftAdrCommand) -> str:
    parts = [cmd.decision_title or "[No title provided]", *cmd.constraints, *cmd.options_to_evaluate]
    return "\n".join(p for p in parts if p)


class DraftAdrHandler:
    def __init__(self, llm: LlmGateway, system_prompt: str, event_bus: EventBus):
        self._llm = llm
        self._system_prompt = system_prompt
        self._event_bus = event_bus

    def handle(self, cmd: DraftAdrCommand) -> ChangeRequestAnalysis:
        subject_text = _subject_text(cmd)
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", cmd.decision_title or "").strip("-").upper() or uuid.uuid4().hex[:8]
        analysis_id = AnalysisId(f"ADR-{slug}"[:64])
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
