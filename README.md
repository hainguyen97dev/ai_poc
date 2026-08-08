# AI POC — Role-Based AI Agents in the SDLC

Proof-of-concept work for applying AI agents across the software development lifecycle, scoped and bounded per role — each agent assists a named human owner rather than replacing their decision.

## Contents

| Path | What it is |
|---|---|
| [introduce.md](./introduce.md) | Role blueprint: Solution Architect's responsibilities, what AI replaces vs. can't replace, the 7-phase delivery workflow, and the role-ownership/human-gate model this POC follows. |
| [lab-01-role-based-ai-agent-guide.md](./lab-01-role-based-ai-agent-guide.md) | Lab 1 guide: how to scope one role-specific agent task, define its boundaries, build a proof of concept, and produce reviewed evidence — the spec this repo's implementation follows. |
| [agent-sa/](./agent-sa/) | **Lab 1 implementation** — Solution Architect agent(s). Two apps: a CLI (`agent.py`, Architecture Impact Analyzer / AIA) and a REST API service (`ada-service/`, Architecture Decision Assistant / ADA), built on a shared DDD + event-driven domain. See [agent-sa/README.md](./agent-sa/README.md) for the full design, folder map, and how to run it. |

## Core Principles (from the Lab 1 guide)

- **Human-led** — a named human owns the final decision and approval.
- **Spec-first** — the agent works from approved or explicitly provided input artifacts.
- **AI-assisted** — the agent drafts, analyzes, or proposes; it never independently approves, merges, releases, or performs irreversible actions.

## Quick Start

The implemented agent lives in `agent-sa/`:

```bash
cd agent-sa
pip install -r requirements.txt
cp .env.example .env && $EDITOR .env   # set LLM_PROVIDER + the matching API key
python3 agent.py --test normal --dry-run
```

Full instructions (Docker, the REST API service, test scenarios): [agent-sa/README.md](./agent-sa/README.md).

## Status

Reference implementation for Lab 1 (Solution Architect role). Other roles from the guide's task table (BA/PO, Developer, QA, DevOps, UX/UI, Data Engineer) are not yet implemented here.
