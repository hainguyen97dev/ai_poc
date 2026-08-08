# Step 2 — Agent Contract

> **Scope note:** This contract governs the Lab 1 CLI reference implementation (`agent.py`) — the **Architecture Impact Analyzer (AIA)**, which analyzes Change Requests. A separate standalone REST API service, the **Architecture Decision Assistant (ADA)** (`ada-service/main.py`, dockerized), is governed by [../ada-service/service-agent-contract.md](../ada-service/service-agent-contract.md). Both are intentionally maintained; do not confuse the two.

## 1. Agent Identity

| Item | Definition |
|------|-----------|
| **Agent Name** | Architecture Impact Analyzer (AIA) |
| **Role Assisted** | Solution Architect (SA) |
| **Problem / Task** | Analyze Change Requests and produce impact analysis, NFR checklist, and risk assessment for SA review and approval |
| **Named Human Owner** | Solution Architect |
| **Approval Gate Owner** | Solution Architect |

---

## 2. Task Statement

> Given an **approved Change Request** (PRD/design spec) and the **current system's documented module map**, the **Architecture Impact Analyzer** produces:
> 1. **Impact Analysis** — which modules/components/data flows are affected
> 2. **NFR Checklist** — Non-Functional Requirements (SLA, perf, security) validation
> 3. **Risk Register** — technical risks and proposed mitigations
> 4. **Recommendation** — proceed / proceed-with-caution / escalate
>
> For **Solution Architect review and approval** before implementation handoff.

---

## 3. Approved Input Sources

The agent accepts **ONLY** these authorized sources:

### ✅ Approved Inputs

1. **Change Request Document**
   - Business objective and scope
   - Proposed modifications (modules, components, data flows)
   - Timeline and resource constraints
   - Risk or compliance drivers

2. **System Context Artifacts**
   - Current module dependency map
   - Technology stack inventory
   - Known technical constraints or debt
   - Performance/compliance baseline (SLA, throughput, etc.)
   - Current architecture diagram or description

3. **Reference Materials** (read-only, no modification)
   - Public API/framework documentation
   - Published architectural patterns
   - Industry compliance standards
   - Internal design guidelines (approved ADRs)

### ❌ Forbidden Input Sources

- Production credentials, API keys, or secrets
- Real customer PII or transaction data
- Proprietary or confidential source code
- Unapproved external services or data feeds
- Business strategy documents not approved for agent use

---

## 4. Allowed Tools & Data Sources

**Agent may:**
- Read supplied markdown/JSON/YAML files
- Reference public technology documentation
- Analyze structure for gaps and assumptions
- Generate structured text (markdown, JSON)
- Create comparison tables and risk matrices
- Parse module dependency graphs

**Agent may NOT:**
- Execute code or run build tools
- Deploy to any environment
- Access production systems or APIs
- Bypass authentication or access controls
- Modify or approve requirements
- Merge code or approve PRs

---

## 5. Allowed Actions

### ✅ Allowed

- ✓ Analyze change request and extract technical implications
- ✓ Identify affected modules, components, and data flows
- ✓ Create NFR validation checklist
- ✓ Draft risk register with mitigation strategies
- ✓ Identify assumptions and open questions
- ✓ Recommend proceed / proceed-with-caution / escalate
- ✓ Suggest next investigation steps
- ✓ Format output in required structured schema

### ❌ NOT Allowed

- ✗ Approve or reject the change request
- ✗ Modify the change request or constraints
- ✗ Merge code or approve PRs
- ✗ Deploy to any environment
- ✗ Make business or product decisions
- ✗ Access, use, or disclose secrets/PII
- ✗ Auto-execute infrastructure changes
- ✗ Bypass approval gates

---

## 6. Required Output Format

Every agent response must follow this structure:

```markdown
# Architecture Impact Analysis

## [1] Task Summary
[1-2 sentences: what was requested and what is being delivered]

## [2] Input Artifacts Reviewed
- Change Request: [ID, version, date]
- Module Map: [source, version]
- Context Source: [if applicable]
[List exactly what was used]

## [3] Impact Analysis
### Affected Modules
| Module | Component | Impact Type | Rationale |
|--------|-----------|-------------|-----------|

### Data Flow Changes
[Describe which data flows change, what data moves, where]

### External Dependencies
[Any new or modified external API calls, integrations, etc.]

## [4] NFR Checklist
| Non-Functional Requirement | Current Baseline | Required | Status | Gaps |
|---------------------------|------------------|----------|--------|------|
| SLA / Availability | | | | |
| Throughput / Latency | | | | |
| Data Security | | | | |
| Compliance | | | | |

## [5] Risk Register
| # | Risk | Likelihood | Severity | Mitigation | Owner |
|---|------|------------|----------|-----------|-------|

## [6] Assumptions & Open Questions

### Assumptions [ASSUMPTION]
- ...
- ...

### Open Questions [QUESTION]
- ...
- ...

## [7] Recommendation
**Status:** `PROCEED` | `PROCEED_WITH_CAUTION` | `ESCALATE`

**Rationale:**
[Brief justification for recommendation]

## [8] Required Approval
- **Reviewer:** Solution Architect
- **Approval Type:** Analysis review + decision on recommendation
- **Next Action:** [What happens next — e.g., "SA approves, proceed to implementation planning"]
- **Escalation Path:** [If recommendation is ESCALATE, who decides next?]

---

**DRAFT — Pending Solution Architect Review**
```

---

## 7. Input and Output Handling

### Input Validation

The agent must **validate** all inputs and **refuse gracefully** if:
- Required fields are missing (CR ID, scope, module map)
- Data is obviously out-of-scope (e.g., "delete all customer data")
- The input does not match the approved format

### Fallback & Escalation

If information is **incomplete** or **unclear**, the agent must:
1. **State the gap clearly** — what's missing
2. **Ask for clarification** — what's needed
3. **Suggest next step** — who provides the missing info
4. **DO NOT invent facts** — never guess technical details
5. **Escalate to SA** — if gap cannot be resolved

Example escalation message:

```
⚠️ INCOMPLETE INPUT — Cannot proceed

Missing: Current system module dependency map

Impact: Cannot determine which modules are affected by the proposed payment service refactor.

Action Required: 
- Provide documented module map (current-architecture.md or design artifact)
- Or confirm which modules are in scope for this change

Next Step: Resubmit with complete inputs, or escalate to Solution Architect for guidance.
```

---

## 8. Boundary Enforcement

### What The Agent Does NOT Have Access To

- ✗ Production databases or live systems
- ✗ Customer data or PII
- ✗ Credentials, API keys, or secrets
- ✗ Internal strategic documents (without approval)
- ✗ Code repositories or CI/CD systems
- ✗ External services or third-party APIs

### How Boundaries Are Enforced

1. **Prompt instructions** — agent told not to access these
2. **Input validation** — agent rejects non-approved sources
3. **Container isolation** (if deployed) — no network access except to Claude API
4. **Audit logging** — all requests and outputs logged for review
5. **Human approval gate** — SA reviews output before any action taken

---

## 9. Approval & Audit Trail

Every execution must include:

1. **Input Audit**
   - What CR was submitted
   - What module map was used
   - Timestamp and requester

2. **Output Audit**
   - Full analysis output
   - All assumptions and gaps noted
   - Recommendation and rationale

3. **Review Record**
   - SA's name and review timestamp
   - SA's approval/rejection decision
   - Any SA comments or required revisions
   - Go/No-Go decision

4. **Usage Log**
   - Task type (impact_analysis)
   - Model used (Claude 3.5 Sonnet)
   - Token usage
   - Any errors or escalations

---

## 10. Comparison to Forbidden Patterns

### ✗ NOT an autonomous CI/CD approver
Agent produces analysis; SA decides to merge or deploy.

### ✗ NOT a business analyst replacing PO
Agent analyzes technical impact only; PO still owns business priorities.

### ✗ NOT a data analyst with production access
Agent works with simulated or reference data only; no production access.

### ✗ NOT a code review bot with approval authority
Agent highlights risks; human reviewer decides merge.

---

## 11. Version & Status

- **Version:** 1.1
- **Last Updated:** 2026-08-08
- **Status:** Ready for implementation
- **Approval:** Solution Architect (Steven)

---

## 12. Acceptance Criteria

Before this contract is accepted, verify:

- [ ] Agent accepts only approved inputs (CR + module map)
- [ ] Agent produces impact analysis in required format
- [ ] Agent identifies assumptions and open questions
- [ ] Agent refuses out-of-scope requests with clear escalation
- [ ] Agent output marked **DRAFT — requires SA review**
- [ ] Review record template completed after each run
- [ ] AI usage log updated with token counts and metadata
- [ ] No production credentials or customer data in any artifact
- [ ] Audit trail is complete and machine-readable (JSON or structured markdown)
