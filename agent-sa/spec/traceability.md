# Traceability — User Journey → Requirement → PR → Release

> Companion to [role-task.md](./role-task.md), [agent-contract.md](./agent-contract.md), and [domain-model.md](./domain-model.md). Answers: *if this were a real product, could you go from "why did we build this" to "what shipped code answers it"?*

## Why this exists

This agent's own bounded context (`ChangeRequestAnalysis`, see [domain-model.md](./domain-model.md)) only covers **Phase 3 — Architecture and Design** of the delivery workflow defined in [introduce.md § 5](../../introduce.md). introduce.md's Technical Specification duty explicitly calls for "maintain the REQ-ID traceability chain from requirement → design → code" — that chain doesn't stop at this agent's output. For a real product, an auditor (or a future engineer) must be able to walk from a shipped Pull Request all the way back to the business requirement it answers, through every human gate in between.

**Status in this repo:** the *fields* for this chain exist (in `AI_USAGE_LOG.md` and, for `requirement_id`, in code — see below). The *values* for the demo runs are honestly marked `TBD` — there is no real requirement ticket or PR behind this lab's sample data, and this repo does not fabricate one. Fill them in when a real requirement and PR exist.

## The Chain

```
User Journey / Epic          (business intent — e.g. a product backlog epic)
        │
        ▼
Phase 1 — Requirement Intake  → REQ-ID            Owner: BA / PO
        │                                          Human gate: PO approves requirement baseline
        ▼
Phase 3 — Architecture & Design → CR-ID / Analysis  Owner: Solution Architect — THIS AGENT'S SCOPE
        │  (agent-sa produces the impact analysis / ADR draft; SA approves)
        ▼
Phase 4 — Implementation Planning → Task breakdown  Owner: Tech Lead
        │
        ▼
Phase 5 — Implementation      → PR(s)               Owner: BE/FE/App engineers
        │                                            Human gate: code review before merge
        ▼
Phase 6 — Validation          → Test evidence        Owner: QA
        │
        ▼
Phase 7 — Approval & Release  → Release/deploy tag    Owner: PO / Eng Lead / Governance
```

(Phase numbers match [introduce.md § 5 Common Delivery Workflow](../../introduce.md) and § 6's Role Ownership Model.)

## What's captured where

| Link in the chain | Field | Where it lives | Who fills it | Automated? |
|---|---|---|---|---|
| Epic → Requirement | `REQ-ID` | `AI_USAGE_LOG.md` entry header | BA/PO, at requirement intake | No — upstream of this agent |
| Requirement → Analysis | `requirement_id` | `domain.events.DomainEvent.requirement_id`, threaded through every Command in both apps | Whoever submits the CR/requirement to the agent | **Yes** — captured automatically once supplied, logged by `AuditLogListener` |
| Analysis → CR-ID | `analysis_id` | `domain.value_objects.AnalysisId` | This agent | Yes — this is the agent's own primary key |
| Analysis → PR(s) | `Implementation PR(s)` | `AI_USAGE_LOG.md` entry, added **after** the fact | Tech Lead / engineers, once implementation lands | No — outside agent boundaries (agent-contract.md § 5: "Merge code or approve PRs" is NOT Allowed) |
| PR → Release | `Release/Deploy Tag` | `AI_USAGE_LOG.md` entry | PO / Eng Lead, at Phase 7 Go/No-Go | No |

## Why the agent can't (and shouldn't) auto-fill PR/Release

The agent produces its analysis in Phase 3, before implementation exists — a PR literally cannot exist yet when the agent runs. Auto-discovering and attaching a PR later would mean the agent watching a code repository and correlating merges back to analyses, which is:

1. Outside its approved tool access (agent-contract.md § 4: no repo/CI access), and
2. A second, separate integration (GitHub API polling/webhooks) that hasn't been scoped, authorized, or built.

So this repo treats PR/Release linking as a **manual close-the-loop step**, same spirit as `evidence/review-record.md` — a human updates the `AI_USAGE_LOG.md` entry once the PR merges. If a team wants to automate this later, the natural hook is a CI job that appends the PR URL to the matching `AI_USAGE_LOG.md` entry (matched by `CR-ID`) on merge — deliberately not built here.

## Using this for real

1. When submitting a CR/requirement to either app, pass `requirement_id` (AIA: `RequestImpactAnalysisCommand.requirement_id`; ADA: `ArchitectureRequest.requirement_id`, already on the HTTP schema).
2. The audit log line (`AI_USAGE_LOG.md`, machine-appended by `AuditLogListener`) will carry `req=<REQ-ID>` alongside the analysis id automatically.
3. Once SA approves (`evidence/review-record.md`) and implementation ships, a human adds the `Implementation PR(s)` and `Release/Deploy Tag` fields to that run's `AI_USAGE_LOG.md` entry by hand.
