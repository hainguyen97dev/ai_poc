#!/usr/bin/env python3
"""
Architecture Decision Assistant (ADA) - API Service (thin FastAPI adapter)

This file only does HTTP concerns: request/response models, routing, status
codes. All business logic lives in the shared ../domain/ (aggregates, events,
validation) and this app's own features/ (one vertical slice per task type).
See ../spec/domain-model.md and service-agent-contract.md for the design.
"""

import dataclasses
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Make both dependency roots importable whether this file sits at
# agent-sa/ada-service/main.py (local dev) or has been flattened to
# /app/main.py by the Dockerfile.  The ADA directory must take precedence so
# `features.*` resolves to ada-service/features rather than the AIA package at
# agent-sa/features.
_here = Path(__file__).resolve().parent
_shared_root = None
for _candidate in (_here, _here.parent):
    if (_candidate / "domain").is_dir():
        _shared_root = _candidate
        break

if _shared_root is not None:
    for _path in (_shared_root, _here):
        if str(_path) not in sys.path:
            sys.path.insert(0, str(_path))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum

from infra.env import load_env_file
from infra.architecture_context import load_current_architecture
from infra.logging_config import configure_ada_logging

# .env lives at agent-sa/ root. In Docker, real env vars are injected directly
# by `docker run -e` / docker-compose's env_file — no .env file is baked into
# the image (see .dockerignore) — so this is mainly for local (non-Docker) dev.
for _env_candidate in (_here.parent / ".env", _here / ".env"):
    load_env_file(_env_candidate)

from domain.aggregates import AnalysisStatus
from domain.events import (
    AnalysisBlocked,
    AnalysisCompleted,
    OutOfScopeRequestRejected,
    PromptInjectionDetected,
)
from domain.session import Session
from features.analyze_requirement.command import AnalyzeRequirementCommand
from features.analyze_requirement.handler import AnalyzeRequirementHandler
from features.chat_session.command import RefineDraftCommand, SendChatMessageCommand
from features.chat_session.errors import SessionDraftUnavailableError, SessionNotFoundError
from features.chat_session.refine_draft_handler import RefineDraftHandler
from features.chat_session.send_message_handler import SendChatMessageHandler
from features.draft_adr.command import DraftAdrCommand
from features.draft_adr.handler import DraftAdrHandler
from features.gap_impact_analysis.command import RunGapImpactAnalysisCommand
from features.gap_impact_analysis.handler import RunGapImpactAnalysisHandler
from infra.event_bus import EventBus
from infra.gateway_factory import get_llm_gateway
from infra.listeners import AuditLogListener
from infra.session_store import SqliteSessionRepository

# ============================================================================
# Configuration
# ============================================================================

_USAGE_LOG_NAME = "AI_USAGE_LOG.md"
AI_USAGE_LOG = _here.parent / _USAGE_LOG_NAME if (_here.parent / _USAGE_LOG_NAME).exists() else _here / _USAGE_LOG_NAME
LOG_DIR = Path(os.getenv("ADA_LOG_DIR", str((_shared_root or _here) / "logs")))
logger = configure_ada_logging(LOG_DIR)

PROMPT_FILE = Path("/app/sa-agent-prompt.md")
if not PROMPT_FILE.exists():
    PROMPT_FILE = _here / "sa-agent-prompt.md"  # local dev fallback
try:
    SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    SYSTEM_PROMPT = """You are the Architecture Decision Assistant (ADA), a specialized AI agent
that assists Solution Architects in producing architecture options, impact analysis, and ADRs.

Your job is NOT to decide. Your job is to analyze, draft, and present options for human review and approval."""

llm_gateway = get_llm_gateway()  # provider chosen via LLM_PROVIDER in .env (default: anthropic)
session_repo = SqliteSessionRepository()  # chat/draft-version history — see infra/session_store.py

# ============================================================================
# Data Models (HTTP contract — unchanged from previous version)
# ============================================================================


class TaskType(str, Enum):
    ANALYZE_REQUIREMENT = "analyze_requirement"
    GAP_IMPACT_ANALYSIS = "gap_impact_analysis"
    DRAFT_ADR = "draft_adr"


class ContextData(BaseModel):
    as_is_architecture: Optional[str] = None
    tech_stack: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    known_issues: Optional[list[str]] = None
    affected_modules: Optional[list[str]] = None
    current_design_doc: Optional[str] = None
    options_to_evaluate: Optional[list[str]] = None


class ArchitectureRequest(BaseModel):
    task_type: TaskType
    requirement_id: Optional[str] = None
    change_request_id: Optional[str] = None
    decision_title: Optional[str] = None
    requirement_doc: Optional[str] = Field(None, description="Full requirement document in markdown")
    change_description: Optional[str] = None
    context: ContextData = Field(default_factory=ContextData)
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4000


class ReviewRecord(BaseModel):
    reviewer_name: str
    sa_approval: bool
    comments: Optional[str] = None
    required_revisions: Optional[list[str]] = None


class ArchitectureResponse(BaseModel):
    task_type: str
    request_id: str  # human-facing id (requirement_id / change_request_id / decision slug) — may repeat across runs
    session_id: str  # unique per run — use this (not request_id) to open/chat/refine a session
    timestamp: str
    status: str
    analysis: str
    reasoning: Optional[str] = None
    assumptions_count: int
    questions_count: int
    risks_count: int
    review_status: str = "PENDING"
    next_reviewer: str = "Solution Architect"


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str
    reasoning: Optional[str] = None


class DraftVersionResponse(BaseModel):
    version_no: int
    analysis_id: str
    status: str
    content: str
    assumptions_count: int
    questions_count: int
    risks_count: int
    created_at: str
    reasoning: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    task_type: str
    requirement_id: Optional[str]
    subject_ref: str
    status: str
    created_at: str
    updated_at: str
    versions: List[DraftVersionResponse]
    messages: List[ChatMessageResponse]


class SessionSummaryResponse(BaseModel):
    id: str
    task_type: str
    requirement_id: Optional[str]
    subject_ref: str
    status: str
    created_at: str
    updated_at: str
    latest_version_no: Optional[int]
    message_count: int


class UsageResponse(BaseModel):
    total: int
    by_kind: Dict[str, int]  # task_type name -> count, plus a "chat_reply" entry


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Architecture Decision Assistant (ADA)",
    description="AI-assisted architecture analysis for Solution Architects",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def log_startup() -> None:
    logger.info(
        "service_started provider=%s model=%s gateway_available=%s log_file=%s",
        type(llm_gateway).__name__,
        getattr(llm_gateway, "model", "unknown"),
        llm_gateway.is_available(),
        LOG_DIR / "ada.log",
    )


@app.middleware("http")
async def log_request(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    should_log = request.url.path != "/health"
    if should_log:
        logger.info(
            "http_request_started request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http_request_failed request_id=%s method=%s path=%s duration_ms=%d",
            request_id,
            request.method,
            request.url.path,
            int((time.perf_counter() - started_at) * 1000),
        )
        raise
    response.headers["X-Request-ID"] = request_id
    if should_log:
        logger.info(
            "http_request_completed request_id=%s method=%s path=%s status=%s duration_ms=%d",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            int((time.perf_counter() - started_at) * 1000),
        )
    return response

# ============================================================================
# Handler dispatch — one slice per task type, event bus wired once
# ============================================================================


def _build_event_bus() -> EventBus:
    bus = EventBus()
    audit = AuditLogListener(AI_USAGE_LOG)
    bus.subscribe(AnalysisCompleted, audit.on_completed)
    bus.subscribe(AnalysisBlocked, audit.on_blocked)
    bus.subscribe(OutOfScopeRequestRejected, audit.on_rejected)
    bus.subscribe(PromptInjectionDetected, audit.on_injection_detected)
    return bus


def _persist_session(task_type: str, cmd, analysis) -> str:
    """Create the session shell + v1 draft version right after a normal
    /analyze run, so it shows up in GET /api/v1/sessions. Every run gets a
    session, but chat/refine on a REJECTED or BLOCKED v1 is rejected with a
    409 by features/chat_session (nothing there to discuss or refine).

    Returns the new session's id.

    IMPORTANT: this id is a fresh uuid4, deliberately NOT analysis.id.value.
    analysis.id.value reuses the human-supplied requirement_id / change_request_id
    / decision_title-derived slug (features/*/handler.py), which is allowed to
    repeat across independent runs — e.g. re-running with the same requirement_id
    is exactly how the SA iterates. Sessions must never collide on that, since
    `sessions.id` is a primary key; using analysis.id.value here caused a
    sqlite3.IntegrityError (UNIQUE constraint failed) on the second run with
    any repeated id, which surfaced as a 500 and left the chat panel silently
    bound to the previous run's session — see docs/superpowers/specs/
    2026-08-09-ada-chat-session-design.md changelog.
    """
    session_id = uuid.uuid4().hex
    session_repo.create_session(
        session_id,
        task_type=task_type,
        requirement_id=analysis.requirement_id,
        subject_ref=analysis.subject.text[:80],
        request_json=json.dumps(dataclasses.asdict(cmd)),
    )
    draft = analysis.draft
    if draft is not None:
        session_repo.add_draft_version(
            session_id,
            analysis_id=analysis.id.value,
            status=analysis.status.value,
            content=draft.content,
            reasoning=draft.reasoning,
            assumptions_count=draft.assumptions_count,
            questions_count=draft.questions_count,
            risks_count=draft.risks_count,
        )
    else:
        session_repo.add_draft_version(
            session_id,
            analysis_id=analysis.id.value,
            status=analysis.status.value,
            content=f"[{analysis.status.value}] {analysis.status_reason or ''}".strip(),
            assumptions_count=0,
            questions_count=0,
            risks_count=0,
        )
    return session_id


def _session_response(session: Session) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        task_type=session.task_type,
        requirement_id=session.requirement_id,
        subject_ref=session.subject_ref,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        versions=[DraftVersionResponse(**dataclasses.asdict(v)) for v in session.versions],
        messages=[ChatMessageResponse(**dataclasses.asdict(m)) for m in session.messages],
    )


def _dispatch(request: ArchitectureRequest):
    """Route to the slice for this task_type and run it.

    Returns (analysis, session_id) — the terminal aggregate and the id of the
    session _persist_session just created for it (see that function for why
    session_id is never analysis.id.value).
    """
    event_bus = _build_event_bus()
    ctx = request.context
    current_architecture = load_current_architecture()

    def with_baseline(request_context: Optional[str]) -> Optional[str]:
        parts = []
        if current_architecture.is_loaded:
            parts.append(
                "TARGET-SYSTEM CURRENT ARCHITECTURE BASELINE:\n"
                "Treat every item marked [ASSUMPTION] or ASSUMED / UNVERIFIED as unverified. "
                "Do not present it as fact; surface it in assumptions/open questions and require confirmation.\n\n"
                + current_architecture.content
            )
        if request_context:
            parts.append("REQUEST-SPECIFIC CONTEXT:\n" + request_context)
        return "\n\n=====\n\n".join(parts) or None

    # request.requirement_id is the upstream REQ-ID (spec/traceability.md) —
    # passed through as-is, never defaulted to a fake-looking value. When
    # absent, each handler still auto-generates its own analysis id (a run
    # needs *a* primary key), but the aggregate's requirement_id stays None
    # so the audit log honestly shows "TBD" instead of a fabricated REQ-ID.

    if request.task_type == TaskType.ANALYZE_REQUIREMENT:
        cmd = AnalyzeRequirementCommand(
            requirement_id=request.requirement_id,
            requirement_doc=request.requirement_doc,
            as_is_architecture=with_baseline(ctx.as_is_architecture),
            tech_stack=ctx.tech_stack or [],
            constraints=ctx.constraints or [],
            known_issues=ctx.known_issues or [],
        )
        analysis = AnalyzeRequirementHandler(llm_gateway, SYSTEM_PROMPT, event_bus).handle(cmd)
        session_id = _persist_session(request.task_type.value, cmd, analysis)
        return analysis, session_id

    if request.task_type == TaskType.GAP_IMPACT_ANALYSIS:
        cmd = RunGapImpactAnalysisCommand(
            change_request_id=request.change_request_id or "CR-AUTO",
            change_description=request.change_description,
            affected_modules=ctx.affected_modules or [],
            current_design_doc=with_baseline(ctx.current_design_doc),
            requirement_id=request.requirement_id,
        )
        analysis = RunGapImpactAnalysisHandler(llm_gateway, SYSTEM_PROMPT, event_bus).handle(cmd)
        session_id = _persist_session(request.task_type.value, cmd, analysis)
        return analysis, session_id

    if request.task_type == TaskType.DRAFT_ADR:
        cmd = DraftAdrCommand(
            decision_title=request.decision_title,
            options_to_evaluate=ctx.options_to_evaluate or [],
            constraints=ctx.constraints or [],
            current_architecture=with_baseline(None),
            requirement_id=request.requirement_id,
        )
        analysis = DraftAdrHandler(llm_gateway, SYSTEM_PROMPT, event_bus).handle(cmd)
        session_id = _persist_session(request.task_type.value, cmd, analysis)
        return analysis, session_id

    raise ValueError(f"Unknown task type: {request.task_type}")


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Architecture Decision Assistant (ADA)",
        "version": "1.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/analyze", response_model=ArchitectureResponse)
async def analyze_architecture(request: ArchitectureRequest):
    """
    Analyze requirements and generate architecture options, gap/impact analysis, or an ADR draft.

    Dispatches to the vertical slice for `task_type`. Each slice runs deterministic
    input validation first (secrets/PII rejection, prompt-injection flagging) before
    calling the model — see domain/validation.py.

    **Important:** Output is a DRAFT. Solution Architect must review and approve.
    """
    if not llm_gateway.is_available():
        logger.warning(
            "analysis_unavailable task_type=%s provider=%s model=%s",
            request.task_type.value,
            type(llm_gateway).__name__,
            getattr(llm_gateway, "model", "unknown"),
        )
        raise HTTPException(
            status_code=503,
            detail=f"{type(llm_gateway).__name__} unavailable: missing package or API key. Check .env / LLM_PROVIDER.",
        )

    analysis_started_at = time.perf_counter()
    logger.info(
        "analysis_started task_type=%s subject_id=%s provider=%s model=%s",
        request.task_type.value,
        request.requirement_id or request.change_request_id or "auto",
        type(llm_gateway).__name__,
        getattr(llm_gateway, "model", "unknown"),
    )
    try:
        analysis, session_id = _dispatch(request)
    except Exception as e:
        logger.exception(
            "analysis_failed task_type=%s duration_ms=%d",
            request.task_type.value,
            int((time.perf_counter() - analysis_started_at) * 1000),
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    request_id = request.requirement_id or request.change_request_id or analysis.id.value

    if analysis.status == AnalysisStatus.REJECTED:
        logger.warning(
            "analysis_rejected task_type=%s request_id=%s reason=%r",
            request.task_type.value,
            request_id,
            analysis.status_reason,
        )
        raise HTTPException(status_code=400, detail=f"Request rejected: {analysis.status_reason}")

    draft = analysis.draft
    logger.info(
        "analysis_completed task_type=%s request_id=%s status=%s duration_ms=%d "
        "assumptions=%d questions=%d risks=%d",
        request.task_type.value,
        request_id,
        analysis.status.value,
        int((time.perf_counter() - analysis_started_at) * 1000),
        draft.assumptions_count,
        draft.questions_count,
        draft.risks_count,
    )
    return ArchitectureResponse(
        task_type=request.task_type.value,
        request_id=request_id,
        session_id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="SUCCESS",
        analysis=draft.content,
        reasoning=draft.reasoning,
        assumptions_count=draft.assumptions_count,
        questions_count=draft.questions_count,
        risks_count=draft.risks_count,
        review_status="PENDING",
        next_reviewer="Solution Architect",
    )


@app.post("/api/v1/review")
async def submit_review(request_id: str, review: ReviewRecord):
    """
    Submit a review record for an analysis.

    Solution Architect reviews the draft output and records:
    - Approval decision (approved/needs revision/rejected)
    - Comments
    - Any required revisions

    This creates an audit trail for governance.
    """

    review_record = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reviewer": review.reviewer_name,
        "approval": review.sa_approval,
        "comments": review.comments or "",
        "revisions": review.required_revisions or [],
    }

    # In production, save to database
    return {
        "status": "RECORDED",
        "request_id": request_id,
        "review_timestamp": review_record["timestamp"],
        "next_step": "Implementation Planning" if review.sa_approval else "Revise and Resubmit",
    }


@app.get("/api/v1/status/{request_id}")
async def get_request_status(request_id: str):
    """Get status of a submitted analysis request."""

    # In production, look up from database
    return {
        "request_id": request_id,
        "status": "PENDING_REVIEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "next_reviewer": "Solution Architect",
        "note": "Awaiting SA review and approval",
    }


@app.get("/api/v1/sessions", response_model=List[SessionSummaryResponse])
async def list_sessions():
    """List sessions (chat + draft-version history), most recently updated first."""
    return [
        SessionSummaryResponse(
            id=s.id,
            task_type=s.task_type,
            requirement_id=s.requirement_id,
            subject_ref=s.subject_ref,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
            latest_version_no=s.latest_version.version_no if s.latest_version else None,
            message_count=len(s.messages),
        )
        for s in session_repo.list_sessions()
    ]


@app.get("/api/v1/usage", response_model=UsageResponse)
async def get_usage():
    """How many LLM-invoking requests have actually been made, by kind.

    Derived from persisted draft_versions/messages rows (see
    domain.session.UsageStats), not a separate counter — so it can't drift
    from what's actually in the session store.
    """
    stats = session_repo.get_usage_stats()
    by_kind = dict(stats.by_task_type)
    by_kind["chat_reply"] = stats.chat_replies
    return UsageResponse(total=stats.total, by_kind=by_kind)


@app.get("/api/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Fetch one session's full timeline: every draft version and chat message."""
    session = session_repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return _session_response(session)


@app.post("/api/v1/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_chat_message(session_id: str, request: ChatMessageRequest):
    """Send a chat message; ADA replies conversationally, grounded in the latest
    draft version. Does not itself produce a new draft — see .../refine."""
    if not llm_gateway.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"{type(llm_gateway).__name__} unavailable: missing package or API key. Check .env / LLM_PROVIDER.",
        )
    handler = SendChatMessageHandler(llm_gateway, SYSTEM_PROMPT, session_repo)
    try:
        reply = handler.handle(SendChatMessageCommand(session_id=session_id, message=request.message))
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionDraftUnavailableError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return ChatMessageResponse(
        role=reply.role, content=reply.content, created_at=reply.created_at, reasoning=reply.reasoning
    )


@app.post("/api/v1/sessions/{session_id}/refine", response_model=SessionResponse)
async def refine_draft(session_id: str):
    """Regenerate the draft using the session's chat history as extra context,
    appending a new version. Explicit, SA-triggered — chat replies never do this."""
    if not llm_gateway.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"{type(llm_gateway).__name__} unavailable: missing package or API key. Check .env / LLM_PROVIDER.",
        )
    event_bus = _build_event_bus()
    handler = RefineDraftHandler(llm_gateway, SYSTEM_PROMPT, event_bus, session_repo)
    try:
        handler.handle(RefineDraftCommand(session_id=session_id))
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SessionDraftUnavailableError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    session = session_repo.get_session(session_id)
    assert session is not None  # RefineDraftHandler just wrote to it
    return _session_response(session)


@app.get("/api/v1/sample-inputs")
async def get_sample_inputs():
    """Get sample input payloads for each task type."""

    samples = {
        "analyze_requirement": {
            "task_type": "analyze_requirement",
            "requirement_id": "REQ-001",
            "requirement_doc": "# Integrate VNPT MyVNPT Payment Gateway\n\nBusiness Goal: Enable users to pay using VNPT services...",
            "context": {
                "as_is_architecture": "Monolithic Java backend + PostgreSQL",
                "tech_stack": ["Java", "Spring Boot", "PostgreSQL", "Docker"],
                "constraints": ["SLA 99.9%", "Support 10k req/sec", "Encrypt payment data"],
                "known_issues": ["Legacy DB schema", "Tight coupling in payment module"],
            },
            # Static, illustrative only — never a real LLM call. agent-console's
            # "Load example" renders this alongside the form so a new SA can see
            # what a finished session looks like before running anything for
            # real. See docs/superpowers/specs/2026-08-09-ada-chat-session-design.md.
            "preview": {
                "reasoning": "The requirement asks for a payment gateway integration on top of a "
                "monolithic backend under tight SLA/throughput constraints. Given the existing "
                "tight coupling in the payment module, a big-bang rewrite is riskier than an "
                "adapter that isolates VNPT's API behind a port — that also keeps rollback cheap "
                "if VNPT's sandbox turns out to have gaps the requirement doc doesn't mention. The "
                "10k req/sec figure matters a lot here: if it's sustained rather than peak, the "
                "monolith's coupling stops being a someday-problem and becomes the actual bottleneck.",
                "analysis": "## Architecture Options — VNPT MyVNPT Payment Integration\n\n"
                "**Option A — Anti-corruption layer inside the monolith.** Wrap VNPT's API behind "
                "a `PaymentGateway` port implemented inside the existing Spring Boot app. Least change, "
                "fastest to ship (est. 1-2 sprints), but the payment module's existing coupling to "
                "order and billing code stays exactly as tight as it is today — this option buys time, "
                "it doesn't buy a cleaner architecture.\n\n"
                "**Option B — Extract a standalone payment service.** New deployable, its own datastore, "
                "talks to the monolith over an API instead of in-process calls. Clean boundary and the "
                "only option that actually unblocks independent scaling for the 10k req/sec target, but "
                "a bigger lift (est. 4-6 sprints) given the legacy DB schema has payment and order rows "
                "in the same tables today — that split is the real cost driver, not the VNPT integration itself.\n\n"
                "```mermaid\n"
                "graph TD\n"
                "    Client[Client Apps] --> Monolith[Java Monolith]\n"
                "    subgraph OptA[Option A - Anti-corruption layer]\n"
                "        Monolith --> Port[PaymentGateway Port]\n"
                "        Port --> VNPT[VNPT MyVNPT API]\n"
                "    end\n"
                "    subgraph OptB[Option B - Extracted service]\n"
                "        Monolith -.->|API call, not in-process| PaySvc[Payment Service]\n"
                "        PaySvc --> VNPT\n"
                "        PaySvc --> PayDB[(Payment DB)]\n"
                "    end\n"
                "```\n\n"
                "**Comparison**\n\n"
                "| Criterion | Option A | Option B |\n|---|---|---|\n"
                "| Time to ship | 1-2 sprints | 4-6 sprints |\n"
                "| Unblocks 10k req/sec sustained | No — shares monolith capacity | Yes |\n"
                "| Touches legacy DB schema | No | Yes — payment/order table split required |\n"
                "| Rollback cost if VNPT integration fails | Low (isolated port) | Medium (new deployable to retire) |\n\n"
                "[ASSUMPTION 1] VNPT's sandbox environment mirrors production behavior closely enough "
                "to test against before go-live.\n\n"
                "[ASSUMPTION 2] The legacy DB schema's payment/order coupling is a schema-design issue, "
                "not something downstream reporting jobs depend on directly.\n\n"
                "[QUESTION 1] Is 10k req/sec a peak or sustained figure?\n\n"
                "[QUESTION 2] Is there a target go-live date that rules out Option B's longer timeline "
                "regardless of which is architecturally cleaner?\n\n"
                "| Risk | Likelihood | Mitigation |\n|---|---|---|\n"
                "| Legacy DB schema can't meet SLA under load | Medium | Load-test Option A before committing |\n"
                "| VNPT sandbox diverges from production | Low | Confirm with VNPT's integration team before Option A ships |\n\n"
                "**Recommendation:** PROCEED_WITH_CAUTION with Option A first; revisit Option B once "
                "the coupling actually blocks a deadline, or once [QUESTION 1] confirms sustained load.",
                "assumptions_count": 2,
                "questions_count": 2,
                "risks_count": 2,
                "chat": [
                    {"role": "user", "content": "10k req/sec is sustained, not peak — does that change the recommendation?"},
                    {
                        "role": "assistant",
                        "content": "Yes — sustained 10k req/sec is a strong signal to bring Option B (standalone "
                        "payment service) forward in the timeline rather than treating it as a later revisit, "
                        "since Option A's monolith would need to sustain that load indefinitely, not just survive a spike.",
                        "reasoning": "A sustained figure removes the 'only during a burst' assumption that made "
                        "Option A's stopgap framing reasonable. If the monolith has to hold that throughput "
                        "continuously, the coupling risk compounds daily rather than being a one-off tail risk.",
                    },
                ],
            },
        },
        "gap_impact_analysis": {
            "task_type": "gap_impact_analysis",
            "change_request_id": "CR-042",
            "change_description": "Migrate payment service to microservice architecture",
            "context": {
                "affected_modules": ["payment", "billing", "reporting"],
                "current_design_doc": "Current monolithic architecture with tight coupling...",
            },
            "preview": {
                "reasoning": "Extracting payment touches billing (shared transaction records) and reporting "
                "(reads payment tables directly today, per the current design doc) — the gap analysis needs "
                "to call out reporting's direct DB coupling explicitly, since that's the kind of dependency "
                "that doesn't show up until the migration is already underway. Sequencing matters more than "
                "the extraction itself: whichever downstream consumer is migrated last determines the "
                "rollback plan for the whole change.",
                "analysis": "## Gap & Impact Analysis — CR-042\n\n"
                "**Change:** Migrate payment out of the monolith into its own deployable service.\n\n"
                "```mermaid\n"
                "graph LR\n"
                "    subgraph Current[Current State]\n"
                "        Pay1[payment module] --- Bill1[billing]\n"
                "        Rep1[reporting] -->|direct SQL read| Pay1\n"
                "    end\n"
                "    subgraph Target[Target State]\n"
                "        Pay2[payment service] -->|domain events| Bill2[billing]\n"
                "        Pay2 -->|read API| Rep2[reporting]\n"
                "    end\n"
                "```\n\n"
                "**Detailed gap table**\n\n"
                "| Area | Current State | Gap | Effort |\n|---|---|---|---|\n"
                "| payment | In-process module, shares the monolith's DB connection pool | Needs its own deployable + API contract | High |\n"
                "| billing | Shares DB transaction with payment (same commit) | Needs eventual-consistency handling — no more shared transaction | Medium |\n"
                "| reporting | Reads payment tables directly via SQL | Needs a read API — direct DB access breaks the moment payment's schema moves | Medium |\n"
                "| ops/monitoring | Single deploy pipeline, single dashboard | New service needs its own health checks, alerts, on-call runbook | Low |\n\n"
                "[ASSUMPTION 1] Billing can tolerate eventual consistency for payment status updates — "
                "no code today assumes payment and billing commit atomically.\n\n"
                "[ASSUMPTION 2] Reporting's current SQL access is read-only — no reporting job writes back "
                "to payment tables.\n\n"
                "[QUESTION 1] Does reporting have a hard freshness SLA on payment data today?\n\n"
                "[QUESTION 2] Are there other, undocumented consumers of the payment tables besides "
                "billing and reporting — e.g. ad-hoc analytics queries or a BI tool?\n\n"
                "**Recommendation:** PROCEED_WITH_CAUTION — sequence reporting's read-API migration before "
                "cutting payment over, not after; reporting is the consumer most likely to break silently.",
                "assumptions_count": 2,
                "questions_count": 2,
                "risks_count": 0,
                "chat": [
                    {"role": "user", "content": "Reporting needs data within 5 minutes today — is that a blocker?"},
                    {
                        "role": "assistant",
                        "content": "Not a blocker, but it does rule out a pure event-driven read API unless the "
                        "event backbone can guarantee sub-5-minute delivery — worth confirming that before reporting's "
                        "migration is scheduled, not during it.",
                        "reasoning": "A 5-minute SLA is loose enough for most async replication approaches, but "
                        "tight enough that an unbounded queue or a slow batch sync would violate it silently — "
                        "flagging it now turns a potential outage into a design constraint instead.",
                    },
                ],
            },
        },
        "draft_adr": {
            "task_type": "draft_adr",
            "decision_title": "API Gateway Pattern for VNPT Integration",
            "context": {
                "options_to_evaluate": ["Kong", "AWS API Gateway", "Spring Cloud Gateway"],
                "constraints": ["On-premise deployment required", "Support 10k req/sec"],
            },
            "preview": {
                "reasoning": "On-premise deployment is a hard constraint, which immediately rules out AWS API "
                "Gateway (managed, cloud-only) regardless of its other merits — so the real comparison is "
                "Kong vs. Spring Cloud Gateway, both of which run on-premise. The deciding factor ends up "
                "being how much of the rate-limiting/auth surface is configuration versus custom code, since "
                "that's what actually drives ongoing maintenance cost after launch.",
                "analysis": "## ADR: API Gateway Pattern for VNPT Integration\n\n"
                "**Decision:** Use Kong.\n\n"
                "```mermaid\n"
                "graph TD\n"
                "    Constraints[On-premise + 10k req/sec] --> Kong[Kong]\n"
                "    Constraints --> SCG[Spring Cloud Gateway]\n"
                "    Constraints -.->|excluded| AWS[AWS API Gateway - cloud only]\n"
                "    Kong --> Decision{Decision}\n"
                "    SCG --> Decision\n"
                "    Decision --> Chosen[Kong selected]\n"
                "```\n\n"
                "**Alternatives considered**\n\n"
                "| Option | On-premise? | Rate-limiting/auth | Verdict |\n|---|---|---|---|\n"
                "| AWS API Gateway | No — managed/cloud-only | Built-in | Rejected — violates hard constraint |\n"
                "| Spring Cloud Gateway | Yes | Requires custom Java filters | Viable, more code to own |\n"
                "| Kong | Yes | Built-in declarative plugins | **Selected** |\n\n"
                "Spring Cloud Gateway is fully viable and stays on the table as a fallback — the gap is "
                "operational, not architectural: Kong's plugin ecosystem covers rate-limiting and auth "
                "out of the box, where Spring Cloud Gateway needs custom filter code for the same behavior.\n\n"
                "[ASSUMPTION 1] The team has or can build ops familiarity with Kong (declarative config, "
                "occasional Lua for custom plugins) within the project timeline.\n\n"
                "[ASSUMPTION 2] Kong's own datastore (Postgres or Cassandra) doesn't add meaningfully to the "
                "on-premise ops burden beyond what the team already runs for the monolith.\n\n"
                "**Consequences:** Adds an operational dependency (Kong's own DB); reduces custom gateway code "
                "the team would otherwise have to write and maintain in Spring Cloud Gateway.",
                "assumptions_count": 2,
                "questions_count": 0,
                "risks_count": 0,
                "chat": [
                    {"role": "user", "content": "We don't have Lua experience on the team — does that change the call?"},
                    {
                        "role": "assistant",
                        "content": "It weakens Kong's advantage but doesn't flip the decision — most of Kong's "
                        "common needs (rate-limiting, auth, on-premise routing) are configured via its declarative "
                        "config, not custom Lua, so day-one usage doesn't require Lua fluency. Worth flagging as a "
                        "revised assumption rather than reopening Spring Cloud Gateway.",
                        "reasoning": "Lua is only needed for custom plugin development, not for using Kong's "
                        "built-in plugins — conflating 'no Lua experience' with 'can't use Kong' would be "
                        "overcorrecting on a constraint that doesn't actually bind for this use case.",
                    },
                ],
            },
        },
    }

    return {
        "samples": samples,
        "documentation": "See /api/v1/docs for full API documentation",
    }


@app.get("/api/v1/current-architecture")
async def get_current_architecture():
    """Show the baseline sources ADA will inject into its next request."""
    context = load_current_architecture()
    return {
        "loaded": context.is_loaded,
        "root": str(context.root) if context.root else None,
        "files": list(context.files),
        "character_count": len(context.content),
        "truncated": context.truncated,
        "content": context.content,
    }


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "service": "Architecture Decision Assistant (ADA)",
        "version": "1.1.0",
        "description": "AI-assisted architecture analysis for Solution Architects",
        "endpoints": {
            "health": "/health",
            "analyze": "POST /api/v1/analyze",
            "review": "POST /api/v1/review",
            "status": "GET /api/v1/status/{request_id}",
            "sessions": "GET /api/v1/sessions",
            "usage": "GET /api/v1/usage",
            "session_detail": "GET /api/v1/sessions/{session_id}",
            "session_chat": "POST /api/v1/sessions/{session_id}/messages",
            "session_refine": "POST /api/v1/sessions/{session_id}/refine",
            "samples": "/api/v1/sample-inputs",
            "current_architecture": "/api/v1/current-architecture",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
