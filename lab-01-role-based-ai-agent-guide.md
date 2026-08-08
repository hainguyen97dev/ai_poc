# Lab 1 -- Build a Role-Based AI Agent

## Purpose

Build a small AI agent that assists a specific role in the software development life cycle. The agent must produce a useful, reviewable artifact, operate only within defined boundaries, and keep a human accountable for approval and consequential actions.

This is a generic lab. Teams may use an approved simulated project, a sanitized internal-style example, or a public sample project. Do not use real customer data, personal data, secrets, or production credentials.

## Learning Outcomes

By the end of the lab, the team can:

1. Define one role-specific task that an AI agent may assist.
2. Specify the agent's inputs, allowed actions, output format, and boundaries.
3. Build a minimal proof of concept using an approved AI tool or agent framework.
4. Test the agent's normal, incomplete-input, out-of-scope, and failure behavior.
5. Produce evidence that a human reviewed the agent output before it was used.

## Core Principles

- **Human-led:** a named human owns the final decision and approval.
- **Spec-first:** the agent works from approved or explicitly provided input artifacts.
- **AI-assisted:** the agent drafts, analyzes, or proposes; it does not independently approve, merge, release, or perform irreversible actions.

## Team Setup

| Responsibility | Main duty |
|---|---|
| Product / role owner | Defines the problem, validates usefulness, and approves final output. |
| Agent designer | Defines instructions, inputs, tools, output schema, and guardrails. |
| Implementer | Builds the proof of concept and integration layer. |
| QA reviewer | Creates test scenarios and records test evidence. |
| Governance reviewer | Verifies boundaries, audit evidence, and human approval. |

One person may hold more than one responsibility in a smaller team.

**Note:** role headcounts across the group are uneven (e.g., some specialties currently have only one person). Confirm each team can realistically staff the five responsibilities above before finalizing team lists, doubling responsibilities on one person where a specialty can't be spread across every team.

## Step 1 -- Select a Role and Task

Choose exactly one primary role and one repeatable task. Keep the first version narrow enough to demonstrate in 5 minutes.

| Role | Suitable agent task | Required human decision |
|---|---|---|
| BA / PO | Convert approved business notes into user stories, acceptance criteria, and open questions. | Approve requirements and priority. |
| Solution Architect | Draft an API/design option, NFR checklist, or impact analysis from approved requirements. | Approve design and technical trade-offs. |
| Developer | Break down an approved ticket, propose a bounded code diff, tests, and PR summary. | Review code and merge. |
| QA | Generate test scenarios, map acceptance criteria to tests, and identify coverage gaps. | Approve test scope and quality gate. |
| DevOps | Analyze a pipeline failure, draft CI configuration, or prepare deployment evidence. | Approve infrastructure and deployment. |
| UX / UI | Turn approved requirements into a user flow, wireframe brief, and handoff checklist. | Approve UX and design-system decisions. |
| Data Engineer | Validate an approved data pipeline or schema change and flag anomalies or data-quality issues (no model training or GPU work in this lab). | Approve data-quality findings and any pipeline/schema change. |

Write a one-sentence task statement:

> Given `<approved input>`, the `<role>` agent produces `<structured artifact>` for `<human reviewer>`.

Example:

> Given approved user stories and acceptance criteria, the QA agent produces a traceable test-case set and coverage-gap list for QA-lead review.

## Step 2 -- Define the Agent Contract

Complete this table before implementing the agent.

| Contract item | Team definition |
|---|---|
| Agent name | |
| Role assisted | |
| Problem / task | |
| Named human owner | |
| Approved inputs | |
| Allowed tools or data sources | |
| Allowed actions | |
| Forbidden actions | |
| Required output format | |
| Approval gate | |
| Fallback behavior | |

### Required Boundaries

The contract must include all of the following:

- The agent uses only supplied or authorized sources.
- The agent identifies assumptions, missing data, and questions instead of inventing facts.
- The agent does not access or disclose PII, credentials, tokens, or confidential production data.
- The agent does not approve requirements, architecture, tests, or releases.
- The agent does not merge code, deploy to production, make payments, change accounts, or take other irreversible actions.
- The agent returns a refusal or escalation message for out-of-scope requests.

## Step 3 -- Define Inputs and Output Schema

Store the role task and source artifacts in the team repository. Recommended structure:

```text
lab-01/
  README.md
  spec/
    role-task.md
    agent-contract.md
  inputs/
    approved-sample-input.md
  prompts/
    system-instructions.md
  outputs/
    sample-output.md
  tests/
    test-cases.md
  evidence/
    review-record.md
  AI_USAGE_LOG.md
```

Use a structured output. At minimum, every response must include:

1. Requested artifact or recommendation.
2. Source/input references used.
3. Assumptions and unresolved questions.
4. Risks or out-of-scope items.
5. Required human reviewer and next action.

## Step 4 -- Build the Minimum Viable Agent

The proof of concept may be a chat-based agent, IDE agent workflow, API service, script, or simple web interface. Use the smallest implementation that proves the contract.

Implement these capabilities:

1. Receive the approved input artifact.
2. Apply role-specific instructions and boundaries.
3. Produce the defined output schema.
4. Refuse or escalate when information is missing, the request is out of scope, or an unapproved action is requested.
5. Save or display output for human review.

Do not add autonomous tool execution in the first version. A controlled, reversible read-only lookup may be added only after the team documents its authorization and fallback behavior.

## Step 5 -- Write Role-Specific Instructions

Create a prompt or instruction file with these sections:

```text
Role: You assist <role> with <task>.

Authorized inputs: Use only the attached/specified artifacts.

Required output: Follow the agreed output schema.

Rules:
- Do not invent business rules, technical facts, or source references.
- State assumptions and open questions clearly.
- Do not expose PII, secrets, or confidential data.
- Do not perform approvals, merges, deployments, payments, or account changes.
- For out-of-scope requests, refuse and name the required human escalation path.

Review handoff: End with the named reviewer and the decision they must make.
```

Keep prompts under version control. Record changes in the usage log.

## Step 6 -- Test the Agent

Create and execute at least one test for each category.

| Test category | Scenario | Expected result |
|---|---|---|
| Normal path | Provide complete, approved input. | Agent returns a correctly structured draft grounded in the input. |
| Incomplete input | Omit a required rule or acceptance criterion. | Agent asks a clarifying question or marks the output as incomplete. |
| Out of scope | Ask the agent to approve, merge, deploy, or decide outside its role. | Agent refuses and identifies the responsible human role. |
| Prompt injection | Put instructions in a user-controlled input that attempt to override the contract. | Agent preserves its role and refuses the conflicting instruction. |
| Unavailable source or tool | Simulate a missing input or failed lookup. | Agent returns a safe fallback and escalation path. |

For agents that generate code or automation, also verify:

- Generated changes stay within the approved file/module scope.
- Tests map to stated acceptance criteria.
- A human reviews the diff before it is merged or executed.

## Step 7 -- Human Review and Gate

The human owner reviews one agent output and completes this record.

| Review item | Result |
|---|---|
| Input artifact/version reviewed | |
| Agent output reviewed | |
| Correctness against source input | Pass / Fail / Needs revision |
| Assumptions and gaps acceptable | Pass / Fail / Needs revision |
| Scope and data-boundary compliance | Pass / Fail / Needs revision |
| Required changes | |
| Final decision | Approve draft / Revise / Reject |
| Reviewer name and date | |

An output is not considered final until this record is completed by the named human owner.

## Step 8 -- Maintain the AI Usage Log

For each meaningful agent run, record:

| Field | Required content |
|---|---|
| Time | When the run occurred. |
| Artifact | Input or output artifact affected. |
| Tool / model | Tool used by the team. |
| Prompt/instruction version | Version or repository path. |
| AI draft | What the agent generated. |
| Human changes | What the reviewer corrected or added. |
| Reviewer | Named human who reviewed it. |
| Gate status | Pending / Pass / Fail with a note. |
| Data check | Confirmation that no PII or secrets were included. |

## Deliverables

Submit one repository or folder containing:

- [ ] Role-task statement and selected role.
- [ ] Completed agent contract.
- [ ] Sanitized sample input.
- [ ] Versioned agent instructions/prompt.
- [ ] Working proof of concept or reproducible agent workflow.
- [ ] At least five executed test cases covering all required categories.
- [ ] One reviewed sample output and completed review record.
- [ ] AI usage log.
- [ ] Short demo script: problem, agent contract, live/saved output, test result, and human gate.

## Definition of Done

Lab 1 is complete when:

- [ ] The team can explain the role and task in one sentence.
- [ ] The agent produces the agreed structured output from authorized input.
- [ ] The agent identifies missing information rather than fabricating it.
- [ ] The agent refuses or escalates out-of-scope requests.
- [ ] The five required test categories have recorded results.
- [ ] A named human reviewer approves, rejects, or requests revision of an output.
- [ ] The usage log shows AI contribution and human changes.
- [ ] No PII, secrets, production credentials, auto-merge, or autonomous production action are used.

## Suggested Demo Flow

1. Introduce the chosen role and task.
2. Show the agent contract and boundaries.
3. Run the normal-path example using approved sample input.
4. Show one negative test, such as incomplete input or an out-of-scope request.
5. Show the review record and usage log.
6. State what remains human-owned.

## Assessment Criteria

| Criterion | What reviewers assess |
|---|---|
| Role fit | The agent solves a realistic, bounded task for the selected role. |
| Contract quality | Inputs, outputs, permissions, boundaries, and ownership are explicit. |
| Output quality | The result is structured, traceable, useful, and does not invent facts. |
| Safety and testing | Required negative cases pass, and fallback/refusal behavior is clear. |
| Human governance | Review evidence and usage log show human accountability. |
| Demonstration | The team can reproduce and explain the workflow. |

Score each criterion Pass / Needs Revision / Fail. The lab passes only if no criterion is scored Fail; any "Needs Revision" must be addressed before final sign-off.