# Research schema and conventions

Schema version: 1. Decimal values serialize as JSON strings and SQL text, never binary floats.
UTC ISO timestamps identify audit wall time; monotonic receive nanoseconds apply only inside
a recording/process clock domain. Replay `at_ms` identifies synthetic time since timeline start.

| Table | Keys and fields | Behavior |
| --- | --- | --- |
| records | integer id; indexed kind; globally unique key; schema_version; JSON payload; created_at | Application append-only |
| system_state | primary key; text value | Persistent kill flag |
| reservations | primary key; indexed event_id; exact amount text; active flag | Serialized capacity reservation and reconciled release |

Record kinds currently used: fill, cash_ledger, paper_run and audit. Mapping reads are reserved
for the future approval workflow. Positions derive from durable unique fills; independent
venues remain separate. Cash ledger fill entries contain negative acquisition plus fee deltas.
There are no funded-cash balance assertions or implemented settlement accounting yet.

Domain models include markets, canonical events, books, orientation-specific approvals,
leg quotes, opportunities, synthetic replay events, paper orders and results. Pydantic rejects
extra fields. Book levels require ordered unique prices, positive sizes, nonnegative prices,
noncrossed books and timezone-aware timestamps. Venue-specific grid checks occur at pricing.

A unique venue-qualified fill key prevents duplicate fills and their cash entries from applying
twice. Conflicting duplicate data raises an error. A unique reservation key validates retries
against its original event/amount. Release requires reconciled=true. SQLite BEGIN IMMEDIATE
protects capacity reads and writes from concurrent overspending; storage failures propagate.

The full specification's market/rules/raw-feed, mapping, opportunity, risk, execution, order,
position, settlement and fee-version tables are NOT yet implemented as dedicated ORM tables.
Do not mistake the versioned research envelope for that complete schema. PostgreSQL is not
validated and transaction operations reject it. No SQL retention deletion occurs automatically;
keep audit and fill records for research reproducibility and back up SQLite before manual
archiving. Compressed append-only real-feed recordings remain future M3 work.
