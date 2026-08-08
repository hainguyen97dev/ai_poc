# Solution Architect Role and Agent Blueprint

## 1. Role Summary

Steven: Solution Architect

The Solution Architect is responsible for turning business intent into technical direction, governed design, and delivery-ready architecture. In this context, the architect acts as the bridge between business requirements, domain understanding, system design, implementation execution, and human approval gates.

## 2. Core Responsibilities

- Assessment & Planning: Survey legacy systems and evaluate technical feasibility for integrating the VNPT ecosystem (MyVNPT).
- Architecture Design: Build the High-Level Design (HLD), select the tech stack suitably, publish Architecture Decision Records (ADRs), and enforce NFRs for security and performance.
- Technical Specification: Translate PRDs into spec/design.md, author OpenAPI contracts, and maintain the REQ-ID traceability chain from requirement → design → code.
- Code Governance: Guide dev teams and review/approve GitLab Merge Requests to catch AI drift and architectural flaws before they land.
- Quality Gates: Own the technical risk register and sign the Go/No-Go gate minutes ahead of every release.
- Solution Defense: Present and defend architectural decisions before the Security Board, executive leadership, and external partners.

## 3. What AI Replaces

- Scaffolds spec/design.md, database schemas, and OpenAPI/Swagger specs directly from PRDs.
- Runs automated Gap & Impact analysis on incoming Change Requests, flagging which modules are affected.
- Runs static analysis (SAST) to surface code smells and outdated design patterns.
- Compares pros and cons across tech stacks, libraries, and design patterns to shorten decision time.
- Reads complex log traces and isolates failures fast across the App, API, and Backend layers.

## 4. What AI Cannot Replace

- Final Accountability: The architectural call belongs to a human — and so does ownership when the system goes down.
- Security Boundaries: Enforcing data governance so real VNPT customer data never leaks.
- Strategic Trade-offs: Balancing Time-to-Market against system reliability based on business goals.

## 5. Common Delivery Workflow

The common workflow must connect the following chain:

requirement → domain understanding → architecture → implementation → validation → approval

### Phase 1 — Requirement Intake
- Inputs: PRD, business notes, constraints, goals
- Output: clarified requirement statement and initial scope
- Owner: BA / PO
- Human gate: PO approves the requirement baseline

### Phase 2 — Domain Understanding
- Inputs: requirement artifacts, business rules, context
- Output: domain summary, business scenarios, assumptions, open questions
- Owner: BA / PO as business domain proxy
- Human gate: PO confirms business meaning and priority

### Phase 3 — Architecture and Design
- Inputs: approved requirements and domain understanding
- Output: architecture options, ADR draft, NFR checklist, risk and impact analysis
- Owner: Solution Architect
- Human gate: SA approves design direction before implementation

### Phase 4 — Implementation Planning
- Inputs: approved design and constraints
- Output: task breakdown, ownership mapping, dependency map
- Owner: Tech Lead / Architect / Team Lead
- Human gate: lead review confirms scope and sequencing

### Phase 5 — Implementation
- Inputs: implementation plan and design artifacts
- Output: code changes, contracts, tests, documentation
- Owner: Backend / Frontend / App engineers
- Human gate: review before merge or integration

### Phase 6 — Validation
- Inputs: implementation artifacts and acceptance criteria
- Output: validation report, defects, gap analysis
- Owner: QA / technical reviewer
- Human gate: human confirms validation outcome

### Phase 7 — Approval and Release Readiness
- Inputs: validated implementation and review evidence
- Output: go / no-go decision and release readiness summary
- Owner: Product Owner / Engineering Lead / Governance reviewer
- Human gate: named human approves final readiness

## 6. Role Ownership Model

| Phase | Primary Owner | Supporting Role | Human Gate |
|---|---|---|---|
| Requirement Intake | BA / PO | Stakeholders | PO approval |
| Domain Understanding | BA / PO | SA | PO confirmation |
| Architecture and Design | Solution Architect | BA / PO | SA approval |
| Implementation Planning | Tech Lead | SA | Lead review |
| Implementation | BE / FE / App team | SA | PR / review |
| Validation | QA / Reviewer | BA / PO | Human sign-off |
| Approval | Product / Engineering Lead | Governance | Final approval |

## 7. Agent Role in the Workflow

Agents should act as assistants, not as autonomous decision-makers.

### Allowed assistance
- Draft requirement summaries
- Generate user stories and acceptance criteria
- Produce architecture options and impact analysis
- Draft ADRs or design notes
- Create implementation task breakdowns
- Produce validation checklists

### Not allowed without human approval
- Final business decisions
- Final architecture decisions
- Production deployment
- Access to secrets or restricted data
- Bypassing review gates

## 8. Required Artifacts

To keep the workflow traceable, each delivery should maintain:

- requirement document
- domain notes
- architecture decision record
- implementation plan
- validation evidence
- approval record

## 9. Escalation Rule

If the agent encounters missing information, unclear business rules, risky design choices, or out-of-scope requests, it must:

- state the uncertainty clearly
- ask for clarification
- escalate to the responsible human owner

## 10. Summary

This workflow ensures that work moves from business intent to validated delivery in a controlled and reviewable way. Each phase has a clear owner and a human gate, making it suitable for building role-based agents safely and practically.