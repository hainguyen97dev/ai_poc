"""Session — a persisted timeline of chat + draft versions layered above
ChangeRequestAnalysis runs.

See docs/superpowers/specs/2026-08-09-ada-chat-session-design.md.

Deliberately NOT an aggregate with invariants of its own: each draft version
already IS one immutable `ChangeRequestAnalysis` run (domain/aggregates.py
governs that — "a resubmission is a brand new aggregate instance"). A Session
never mutates a past run; it only appends new versions and messages. These
are plain read/write records, not domain entities with business rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str
    created_at: str
    # The model's reasoning trace behind an "assistant" reply, when the
    # gateway exposed one — always None for "user" messages.
    reasoning: Optional[str] = None


@dataclass(frozen=True)
class DraftVersionRecord:
    version_no: int
    analysis_id: str
    status: str
    content: str
    assumptions_count: int
    questions_count: int
    risks_count: int
    created_at: str
    reasoning: Optional[str] = None


@dataclass(frozen=True)
class Session:
    id: str
    task_type: str
    requirement_id: Optional[str]
    subject_ref: str
    status: str
    # JSON-serialized kwargs of the Command that produced v1 — the snapshot
    # "Refine draft" replays (with conversation folded in), so refine sees
    # exactly the same requirement/context inputs as the original run.
    request_json: str
    created_at: str
    updated_at: str
    versions: Sequence[DraftVersionRecord] = field(default_factory=tuple)
    messages: Sequence[ChatMessage] = field(default_factory=tuple)

    @property
    def latest_version(self) -> Optional[DraftVersionRecord]:
        return self.versions[-1] if self.versions else None


@dataclass(frozen=True)
class UsageStats:
    """How many LLM-invoking requests have actually been made, by kind.

    Deliberately derived from draft_versions/messages (real, already-persisted
    records of completed calls) rather than a separate counter — a counter can
    drift from reality; a count of what's actually in the DB can't.
    """

    # One draft_versions row = one LLM call to generate/refine a draft, keyed
    # by the session's task_type (analyze_requirement / gap_impact_analysis /
    # draft_adr) — a session's v1 and every later "Refine draft" both count.
    by_task_type: Mapping[str, int]
    # One "assistant"-role messages row = one chat-reply LLM call.
    chat_replies: int

    @property
    def total(self) -> int:
        return sum(self.by_task_type.values()) + self.chat_replies
