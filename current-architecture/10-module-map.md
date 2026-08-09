# Assumed Current Module Map

> **Status:** ASSUMED / UNVERIFIED. Dependencies below exist only to make the
> example analyses concrete; they must not be presented as confirmed facts.

| Module | Assumed responsibility | Assumed dependencies |
|---|---|---|
| API / Web | Customer and internal HTTP endpoints | Payment, Billing, Customer, Authentication |
| Payment | Payment initiation, provider calls, transaction state | Billing, Customer, shared database, external payment provider |
| Billing | Invoices, fees, balances, settlement inputs | Payment, Customer, shared database |
| Reporting | Operational and financial reports | Payment and Billing tables in shared database |
| Reconciliation Jobs | Provider reconciliation and retry processing | Payment, Billing, external payment provider, shared database |
| Customer | Customer profile and payment-account references | Authentication, shared database |
| Authentication | Identity and access checks | Customer or identity store |
| Notification | Payment status notifications | Payment, Customer, external email/SMS provider |

## Assumed critical data flows

1. API receives payment request and calls Payment in-process.
2. Payment reads customer/billing data from the shared database.
3. Payment calls the external provider synchronously.
4. Payment and Billing update transaction/invoice records in one database.
5. Reporting reads those transactional records directly.
6. Reconciliation jobs compare provider results with internal records.
7. Notification sends customer-facing status updates.

## Unknowns that require confirmation

- Actual module names and ownership boundaries.
- Whether database tables are truly shared or logically isolated.
- Transaction boundaries between Payment and Billing.
- Retry, idempotency, and reconciliation behavior.
- External provider protocol, timeout, and rate limits.
- Consumers outside the monolith that read payment data.
