# Assumed Target-System Overview

> **Status:** ASSUMED / UNVERIFIED — replace with approved current-state
> documentation when available.

## Business purpose

[ASSUMPTION] The target system supports customer payment initiation, billing,
transaction status tracking, reconciliation, and operational reporting.

## Current architecture

- [ASSUMPTION] The backend is a modular Java Spring Boot monolith.
- [ASSUMPTION] Payment, billing, reporting, and customer-facing APIs are
  deployed as one application unit.
- [ASSUMPTION] The application uses one PostgreSQL database with tables shared
  across module boundaries.
- [ASSUMPTION] Internal module calls are in-process Java calls rather than
  versioned network APIs.
- [ASSUMPTION] External payment-provider integrations are invoked synchronously
  from the payment module.
- [ASSUMPTION] Reporting reads transactional tables directly.

## Current deployment shape

- [ASSUMPTION] One deployable backend artifact is replicated behind a load
  balancer.
- [ASSUMPTION] Database migrations are released with the monolith.
- [ASSUMPTION] Background reconciliation jobs run inside the same application.
- [ASSUMPTION] Logs are centralized, but distributed tracing is not available.

## Evidence required

- Approved current-state architecture diagram.
- Deployment topology and environment inventory.
- Database ownership/schema documentation.
- External integration catalogue.
- Current NFR/SLA baseline and observed production metrics.
