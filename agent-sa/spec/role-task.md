# Step 1 — Role and Task Definition

## Role
**Solution Architect (SA)**

## Task Statement

> Given an **approved Change Request** describing a proposed system modification and the **current system's documented module map**, the **Architecture Impact Analyzer** produces:
> - **Impact Analysis** — which modules and components are affected
> - **NFR Checklist** — Non-Functional Requirements validation
> - **Risk Register** — technical risks and mitigations
> - **Recommendation** — proceed with caution, or escalate
> 
> For **Solution Architect review and approval** before implementation begins.

## Scope

This task is **deliberately narrow** to fit a 5-minute demonstration:

- Input: One Change Request + module map (pre-approved by PO)
- Output: Structured impact analysis (no approval authority)
- Decision gate: Solution Architect reviews analysis and decides proceed/escalate
- No code generation, no deployment, no data access
- Safe to run with simulated data (no customer PII or production credentials)

## Why This Task

From [introduce.md](../../introduce.md), the SA is responsible for:
- **Impact Analysis** on Change Requests ("Runs automated Gap & Impact analysis on incoming Change Requests, flagging which modules are affected")
- **NFR checklist** ("publish ... NFRs for security and performance")
- **Risk Management** ("Own the technical risk register")

This agent **removes the manual analysis overhead** while keeping the approval and strategy decisions human-owned.

## What the SA Still Owns

✅ **Human-Owned Decisions:**
- Approval/rejection of the change
- Trade-off decisions (Time vs. Reliability vs. Cost)
- Sign-off on the impact analysis
- Final Go/No-Go call

## Success Criteria

✓ Agent accepts only approved inputs (CR + module map)  
✓ Agent produces impact analysis in required structured format  
✓ Agent identifies assumptions and missing information  
✓ Agent refuses out-of-scope requests (e.g., "approve this" or "merge this PR")  
✓ Agent output is clearly marked as **DRAFT — requires SA review**  
✓ Human review record is logged and auditable  

## Related Artifacts

- [Agent Contract](./agent-contract.md) — boundaries and controls
- [System Instructions](../prompts/system-instructions.md) — agent behavior rules
- [Sample Input](../inputs/approved-sample-input.md) — real CR example
- [Sample Output](../outputs/sample-output.md) — expected output format
