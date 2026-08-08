"""Event listeners — the side effects that used to be hardcoded inline in
agent.py / main.py. Handlers publish events; these react. Add a new side
effect (e.g. a Slack notification on ESCALATE) by adding a new listener and
subscribing it in the adapter's bootstrap — never by editing a handler.
"""

from __future__ import annotations

from pathlib import Path

from domain.events import (
    AnalysisBlocked,
    AnalysisCompleted,
    OutOfScopeRequestRejected,
    PromptInjectionDetected,
)


class AuditLogListener:
    """Appends one line per terminal/notable event to AI_USAGE_LOG.md.

    Matches agent-contract.md § 9 "Usage Log" / "Audit logging — all requests
    and outputs logged for review".
    """

    def __init__(self, log_file: Path):
        self.log_file = log_file

    def on_completed(self, event: AnalysisCompleted) -> None:
        rec = event.recommendation.value if event.recommendation else "UNSPECIFIED"
        self._append(f"- {event.occurred_at} | {event.analysis_id.value} | COMPLETED | recommendation={rec}")

    def on_blocked(self, event: AnalysisBlocked) -> None:
        self._append(f"- {event.occurred_at} | {event.analysis_id.value} | BLOCKED | reason={event.reason}")

    def on_rejected(self, event: OutOfScopeRequestRejected) -> None:
        self._append(f"- {event.occurred_at} | {event.analysis_id.value} | REJECTED | reason={event.reason}")

    def on_injection_detected(self, event: PromptInjectionDetected) -> None:
        self._append(
            f"- {event.occurred_at} | {event.analysis_id.value} | INJECTION_DETECTED | detail={event.detail}"
        )

    def _append(self, line: str) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


class OutputWriterListener:
    """Writes the draft to outputs/run-<name>.md — only subscribed when the
    CLI is invoked with --save (see agent.py). Dry-run never reaches this;
    dry-run doesn't construct a Command at all.
    """

    def __init__(self, outputs_dir: Path, run_name: str):
        self.outputs_dir = outputs_dir
        self.run_name = run_name

    def on_completed(self, event: AnalysisCompleted) -> None:
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.outputs_dir / f"run-{self.run_name}.md"
        output_file.write_text(event.draft.content, encoding="utf-8")
