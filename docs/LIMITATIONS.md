# Research limitations and live readiness

The supplied data has no empirical market provenance. Synthetic profit is arithmetic, not
measured edge. Latency, liquidity, fees, cancellation and settlement differ in actual markets.
No historical backtest, financial recommendation or live profit claim follows from these runs.

Replay models taker buys, arrival latency plus seeded jitter, price caps, partial fills, missing
historical depth, staleness, closed/disconnected states and versioned per-event fees. It retains
consumption across snapshots rather than assuming replenishment. There is no passive queue
model. Orders must arrive in increasing simulated time. Separate configurable signal, submission,
acknowledgment and hedge latencies, cancel/late-fill simulation, pair recovery, drawdown,
settlement, liquidation valuations, stress loss and capital utilization remain incomplete.

M2 cannot be marked complete until those gaps, durable recovery and end-to-end ledger/report
accounting pass fault tests. M4 includes a local dashboard, protected paper/kill controls,
persistent kill, transactional reservation primitive and mapping validation; it lacks persisted
approval controls, all breakers, operator arming, eligibility and orchestration. M3, M5 and M6
are unimplemented. Stubs deliberately reject all real functionality.

Before live use ALL items below require separate implementation and evidence:

- Verified product/account/location/terms eligibility with authoritative evidence.
- Dated official contracts, fees, rules, units, endpoints, environments and supported SDKs.
- Tested snapshot/bootstrap/reconnect, feed quality, recordings and real read-only smoke tests.
- Complete orientation-specific human approvals and rules-change revocation workflow.
- Live config enablement plus authenticated expiring arm, neither implied by code completion.
- Durable intents, supported external IDs, timeout reconciliation, duplicate-fill protection,
  restart/orphan recovery and safe cancellation with late fills.
- Atomic capacity reservations, all entry/unmatched/venue/event/currency/stress limits and
  circuit breakers, healthy reconciled balances, fresh books and known costs.
- Bounded partial-pair recovery, settlement accounting and honest unavailable liquidation marks.
- Persistent kill that cancels and reconciles external orders, with explicit rearming.
- PostgreSQL transaction tests if used; secure deployment and actual target-environment checks.
- Separate explicit operator authorization for a live run. No such authorization exists here.
