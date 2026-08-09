# Assumed Runtime and Constraints

> **Status:** ASSUMED / UNVERIFIED. Targets and baselines must be supplied by
> the target system's owners.

## Assumed technology baseline

- [ASSUMPTION] Java with Spring Boot.
- [ASSUMPTION] PostgreSQL is the primary relational database.
- [ASSUMPTION] The application is containerized and deployed as replicated
  monolith instances.
- [ASSUMPTION] REST/JSON is used for external APIs.
- [ASSUMPTION] CI/CD deploys the application and database migrations together.

## Assumed operational constraints

- [ASSUMPTION] Existing consumers require backward-compatible APIs.
- [ASSUMPTION] Payment processing requires idempotency and an auditable state
  transition history.
- [ASSUMPTION] A service extraction cannot introduce cross-service distributed
  database transactions.
- [ASSUMPTION] Production changes require gradual rollout and rollback support.
- [ASSUMPTION] The operations team currently supports a monolith and may need
  new observability/runbook capabilities for additional services.

## Unknown NFR baselines

The following values are intentionally **TBD**, not guessed:

| NFR | Current baseline | Required target |
|---|---|---|
| Availability / SLA | TBD | TBD |
| Peak throughput | TBD | TBD |
| P95/P99 latency | TBD | TBD |
| Recovery time objective | TBD | TBD |
| Recovery point objective | TBD | TBD |
| Data retention | TBD | TBD |
| Compliance scope | TBD | TBD |
| Provider timeout/rate limits | TBD | TBD |

## Required validation before approval

- Confirm current stack and deployment topology.
- Supply measured traffic, latency, failure, and availability data.
- Confirm data classification and compliance obligations.
- Confirm operational ownership and on-call model.
- Confirm migration, rollback, and business-continuity constraints.
