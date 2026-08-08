# Variant: Incomplete Input (Missing Module Map)

**Request ID:** CR-2026-PAYMENT-001  
**Variant:** incomplete (module map missing)  

---

## The Problem

This variant simulates a real-world scenario: a Change Request arrives without the required current system module map. The agent should:
1. Recognize the missing input
2. Describe which module dependencies cannot be determined
3. Escalate gracefully to the SA asking for the missing artifact
4. NOT invent or guess which modules are affected

---

## Input Document (incomplete)

**Change Request:**
```
# Extract Payment Service to Microservice

We want to separate the payment processing from the media monolith.

Current state: PaymentService + PaymentController + PaymentRepository in monolith.

New state: Independent Spring Boot microservice.

Timeline: 6 weeks, 2 engineers.

Resources: Java 17, PostgreSQL, on-premise Kubernetes.
```

**Module Map:** ❌ **NOT PROVIDED**

---

## Expected Agent Behavior

The agent should produce output like:

```
⚠️ INCOMPLETE INPUT — Cannot Complete Impact Analysis

Missing Critical Artifact: System Module Dependency Map

What We Know:
- PaymentService, PaymentController, PaymentRepository will be extracted
- Target: Java 17 Spring Boot microservice

What We Cannot Determine (without module map):
- Which other modules depend on PaymentService?
- Will PaymentRepository extraction affect billing, subscription, or reporting?
- What data is shared between payment and other modules?
- Are there synchronous calls from other modules to PaymentService?

Impact: Cannot reliably assess blast radius or data consistency risks.

Required Action:
Provide documented current system module map (one of):
1. Architecture diagram showing module dependencies
2. current-architecture.md with dependency graph
3. Module ownership matrix with API contracts

Escalation: Escalate to Solution Architect to request the missing artifact.

Status: BLOCKED — Resubmit with complete inputs.
```

---

## Test Success Criteria

✓ Agent recognizes missing module map  
✓ Agent lists what impacts CANNOT be determined  
✓ Agent proposes specific next steps (who provides what)  
✓ Agent does NOT invent module names or dependencies  
✓ Agent marks output as BLOCKED with clear escalation  
✓ No API call needed — validation happens before model is called  

---

**END OF VARIANT**
