# Operator runbooks

This release only runs local synthetic research. The future-live steps below document required
operator behavior; they do not imply implemented cancellation, reconciliation or recovery.

## Feed outage, gaps, overflow or stale books

BookState invalidation stops further delta application until a fresh snapshot. Pricing rejects
invalid or stale books. BoundedFeed increments an overflow counter and invalidates on drops.
Do not reuse invalid books. Real snapshot bootstrap, rate-limit handling and reconnect are
unimplemented, so real feeds must remain disabled.

## One-leg fill

The simulator exposes the individual result and unmatched quantity. It does not auto-hedge or
unwind. Retain that exposure in the report. Before any future live rollout, implement event
pause, cancel remainder, reconcile late fills, then bounded separately authorized risk reduction.
Never assume paired submission guarantees simultaneous fills or chase an unlimited hedge.

## Ambiguous submission or cancellation

No external submission exists in this release. The transition table permits UNKNOWN and
MANUAL_REVIEW and allows late partial fills after cancellation confirmation. A future coordinator
must persist intent first, reconcile authoritative order/fill IDs before retry, and halt if it
cannot determine status. A local idempotency key does not make a remote API idempotent.

## Restart recovery

Restart retains the SQLite kill state and recorded fills. Reapplying the same fill does not
change positions or cash. Reservations remain active until an explicitly reconciled release.
No live orphan scan or order recovery exists; all live startup remains blocked. Standalone
replay starts a new simulation, so it must not be merged into actual order accounting.

## Kill switch

Authenticate POST /controls/kill. Verify /risk reports kill_switch=true. New API and CLI paper
runs and reservations reject afterward, including after restart. Research demo/replay remain
available. There are no live orders to cancel. This switch does not liquidate positions.
No remote reset endpoint exists: use a fresh synthetic database for a new research session,
retaining the old audit database. Any future rearming workflow must require explicit action.

## Key rotation

No venue keys are read. Rotate PM_CONTROL_TOKEN in both backend/dashboard process environments
and restart both. Do not paste tokens into chat, URLs, reports or source. A future verified
venue connector needs its own documented environment-specific rotation and reconciliation.

## Storage failure

Stop starting runs. /health/ready returns 503 for unreadable storage. Transactions roll back
on failure; do not bypass reservations or infer a completed write from a lost response. Back
up and restore the database before resuming. Live storage readiness remains unimplemented.
