#!/usr/bin/env python3
"""
Architecture Decision Assistant (ADA) - API Service (thin FastAPI adapter)

This file only does HTTP concerns: request/response models, routing, status
codes. All business logic lives in the shared ../domain/ (aggregates, events,
validation) and this app's own features/ (one vertical slice per task type).
See ../spec/domain-model.md and service-agent-contract.md for the design.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Make `domain` / `infra` importable whether this file sits at
# agent-sa/ada-service/main.py (local dev — they're one level up) or has been
# flattened to /app/main.py by the Dockerfile (they're siblings, COPYd in
# alongside it). Whichever directory actually has `domain/` wins.
_here = Path(__file__).resolve().parent
for _candidate in (_here, _here.parent):
    if (_candidate / "domain").is_dir():
        sys.path.insert(0, str(_candidate))
        break

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum

from infra.env import load_env_file

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
from features.analyze_requirement.command import AnalyzeRequirementCommand
from features.analyze_requirement.handler import AnalyzeRequirementHandler
from features.draft_adr.command import DraftAdrCommand
from features.draft_adr.handler import DraftAdrHandler
from features.gap_impact_analysis.command import RunGapImpactAnalysisCommand
from features.gap_impact_analysis.handler import RunGapImpactAnalysisHandler
from infra.event_bus import EventBus
from infra.gateway_factory import get_llm_gateway
from infra.listeners import AuditLogListener

# ============================================================================
# Configuration
# ============================================================================

_USAGE_LOG_NAME = "AI_USAGE_LOG.md"
AI_USAGE_LOG = _here.parent / _USAGE_LOG_NAME if (_here.parent / _USAGE_LOG_NAME).exists() else _here / _USAGE_LOG_NAME

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
    request_id: str
    timestamp: str
    status: str
    analysis: str
    assumptions_count: int
    questions_count: int
    risks_count: int
    review_status: str = "PENDING"
    next_reviewer: str = "Solution Architect"


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


def _dispatch(request: ArchitectureRequest):
    """Route to the slice for this task_type and run it. Returns the terminal aggregate."""
    event_bus = _build_event_bus()
    ctx = request.context

    # request.requirement_id is the upstream REQ-ID (spec/traceability.md) —
    # passed through as-is, never defaulted to a fake-looking value. When
    # absent, each handler still auto-generates its own analysis id (a run
    # needs *a* primary key), but the aggregate's requirement_id stays None
    # so the audit log honestly shows "TBD" instead of a fabricated REQ-ID.

    if request.task_type == TaskType.ANALYZE_REQUIREMENT:
        handler = AnalyzeRequirementHandler(llm_gateway, SYSTEM_PROMPT, event_bus)
        return handler.handle(
            AnalyzeRequirementCommand(
                requirement_id=request.requirement_id,
                requirement_doc=request.requirement_doc,
                as_is_architecture=ctx.as_is_architecture,
                tech_stack=ctx.tech_stack or [],
                constraints=ctx.constraints or [],
                known_issues=ctx.known_issues or [],
            )
        )

    if request.task_type == TaskType.GAP_IMPACT_ANALYSIS:
        handler = RunGapImpactAnalysisHandler(llm_gateway, SYSTEM_PROMPT, event_bus)
        return handler.handle(
            RunGapImpactAnalysisCommand(
                change_request_id=request.change_request_id or "CR-AUTO",
                change_description=request.change_description,
                affected_modules=ctx.affected_modules or [],
                current_design_doc=ctx.current_design_doc,
                requirement_id=request.requirement_id,
            )
        )

    if request.task_type == TaskType.DRAFT_ADR:
        handler = DraftAdrHandler(llm_gateway, SYSTEM_PROMPT, event_bus)
        return handler.handle(
            DraftAdrCommand(
                decision_title=request.decision_title,
                options_to_evaluate=ctx.options_to_evaluate or [],
                constraints=ctx.constraints or [],
                requirement_id=request.requirement_id,
            )
        )

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
        raise HTTPException(
            status_code=503,
            detail=f"{type(llm_gateway).__name__} unavailable: missing package or API key. Check .env / LLM_PROVIDER.",
        )

    try:
        analysis = _dispatch(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    request_id = request.requirement_id or request.change_request_id or analysis.id.value

    if analysis.status == AnalysisStatus.REJECTED:
        raise HTTPException(status_code=400, detail=f"Request rejected: {analysis.status_reason}")

    draft = analysis.draft
    return ArchitectureResponse(
        task_type=request.task_type.value,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="SUCCESS",
        analysis=draft.content,
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
        },
        "gap_impact_analysis": {
            "task_type": "gap_impact_analysis",
            "change_request_id": "CR-042",
            "change_description": "Migrate payment service to microservice architecture",
            "context": {
                "affected_modules": ["payment", "billing", "reporting"],
                "current_design_doc": "Current monolithic architecture with tight coupling...",
            },
        },
        "draft_adr": {
            "task_type": "draft_adr",
            "decision_title": "API Gateway Pattern for VNPT Integration",
            "context": {
                "options_to_evaluate": ["Kong", "AWS API Gateway", "Spring Cloud Gateway"],
                "constraints": ["On-premise deployment required", "Support 10k req/sec"],
            },
        },
    }

    return {
        "samples": samples,
        "documentation": "See /api/v1/docs for full API documentation",
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
            "samples": "/api/v1/sample-inputs",
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
