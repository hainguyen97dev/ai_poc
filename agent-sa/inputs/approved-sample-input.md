# Sample Change Request — VNPT Payment Service Microservice Extraction

**Request ID:** CR-2026-PAYMENT-001  
**Date Submitted:** 2026-08-08  
**Status:** Approved by PO  
**Module Map Version:** current-architecture.md v2.1  

---

## Executive Summary

Current monolithic architecture creates performance and scaling bottlenecks in payment processing. Proposal: extract Payment Service into independent microservice to enable:
- Autonomous scaling for payment tier
- Faster iteration on payment features
- Clearer failure isolation (payment down ≠ media down)

---

## Business Objective

Enable 50% faster feature deployment for payment integrations (VNPT MyVNPT, credit card, e-wallet) without blocking the core media platform.

---

## Proposed Changes

### In-Scope Modules

1. **PaymentService** (extraction)
   - Current: Monolith `com.vnpt.media.payment.*`
   - Target: Spring Boot microservice `payment-svc`
   - New repo: `vnpt-media/payment-service` (git submodule)

2. **PaymentRepository** (extraction)
   - Current: PostgreSQL `media.transactions` table
   - Target: Dedicated PostgreSQL schema `payment.transactions` (same cluster)
   - Migration: async sync of historical data

3. **PaymentController** (extraction)
   - Current: `/api/v1/payments/*` in monolith
   - Target: `/api/v1/payments/*` routed via API Gateway to payment-svc

### Out-of-Scope

- ❌ Subscription/billing logic (stays in monolith for now)
- ❌ Payment UI components (client code stays in frontend)
- ❌ Third-party payment gateway integrations (no new vendors, only VNPT MyVNPT for now)

---

## Technical Constraints

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| **Tech Stack** | Java 17, Spring Boot 3.0, PostgreSQL 12 | Must match existing team expertise |
| **Deployment** | On-premise Kubernetes | VNPT policy: no public cloud |
| **Network** | Private VPN only, no external access | Security requirement |
| **Data** | Transaction data only, no customer PII in payment-svc | GDPR compliance |
| **Authentication** | OAuth2 token from API Gateway | No direct DB access from client |

---

## Timeline & Resources

| Phase | Duration | Team |
|-------|----------|------|
| Design & Planning | 2 weeks | 1 SA, 1 TL |
| Implementation | 4 weeks | 2 BE engineers |
| Testing & Integration | 2 weeks | 2 QA, 1 BE |
| Deployment Prep | 1 week | 1 DevOps, 1 SA |
| **Total** | **9 weeks** | 2–3 FTE |

---

## Expected Benefits

✓ Payment processing latency: 200ms → 80ms (p95)  
✓ Payment feature deployment: 2 weeks → 4 days  
✓ Payment tier horizontal scaling independent of media tier  
✓ Clearer error isolation: payment failures no longer cascade to media playback  

---

## Known Risks & Dependencies

- **Risk 1:** Data consistency between payment-svc and monolith during transition
- **Risk 2:** Increased operational complexity (2 deployments instead of 1)
- **Dependency:** Requires API Gateway re-routing capability (owned by Platform team)
- **Dependency:** Requires new PostgreSQL schema and user permissions (owned by DBA)

---

## Approval & Sign-Off

- **PO:** Jane Doe (2026-08-01) ✅
- **TL:** Approved in principle, awaiting impact analysis
- **SA:** *[To be completed after impact analysis]*

---

## Appendix A — Current Module Map

See: [current-architecture.md](./module-map-v2.1.md)

Summary:
```
Monolith (com.vnpt.media.*)
├── payment/          ← EXTRACT THIS
│   ├── PaymentService
│   ├── PaymentController
│   └── PaymentRepository
├── billing/          ← KEEP (for now)
├── media/            ← KEEP
├── auth/             ← KEEP
└── integration/      ← KEEP
```

---

## Appendix B — System Baseline (Pre-Change)

- **Deployment:** Single Tomcat/Spring Boot JAR
- **Database:** Single PostgreSQL 12 instance, schema `media.*`
- **API Gateway:** Kong, routes all requests to monolith
- **Throughput:** 2,000 req/s (peak), payment calls = 5% of traffic = 100 req/s
- **Latency:** Payment end-to-end: 200ms (p95)
- **SLA:** 99.9% availability (media + payments combined)

---

## Next Steps

1. **[This Step]** SA produces impact analysis
2. SA reviews and approves impact analysis
3. TL breaks down work into implementation tasks
4. Developers implement + test
5. QA validates, security reviews
6. DevOps prepares deployment plan
7. Go/No-Go gate (PO + SA + TL + OpsLead)
8. Controlled deployment

---

**END OF CHANGE REQUEST**
