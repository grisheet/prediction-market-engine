# Venue API verification

Status recorded 2026-11-14. **No official API pages were retrieved or contract-verified during
this build.** URLs below come from the supplied specification. They are starting points, not
evidence of current shapes. No venue SDK, host, fee formula, sequence protocol, order type,
authentication scheme, minimum, sandbox, rate limit or eligibility determination is implemented.

| Product | Documentation source | Contract status | Read smoke test | Execution |
| --- | --- | --- | --- | --- |
| Kalshi, each environment independently | https://docs.kalshi.com/ | UNVERIFIED | Not run | Disabled |
| Kalshi WebSockets | https://docs.kalshi.com/websockets | UNVERIFIED | Not run | Disabled |
| Kalshi bootstrap | https://docs.kalshi.com/getting_started/quick_start_websockets | UNVERIFIED | Not run | Disabled |
| Polymarket international API | https://docs.polymarket.com/getting-started/api | UNVERIFIED | Not run | Disabled |
| Polymarket market data | https://docs.polymarket.com/market-data/realtime-data | UNVERIFIED | Not run | Disabled |
| Polymarket restrictions | https://docs.polymarket.com/api-reference/geoblock | UNVERIFIED | Not run | Disabled |
| Any distinct U.S. Polymarket product | No product-specific contract verified | UNVERIFIED | Not run | Disabled |
| Local mock | Repository fixture and synthetic-v1 fee schedule | Tested locally | Offline only | Synthetic simulation |

Before implementation, separately verify each product/account/environment: documentation date,
SDK release and signature, authentication and key handling, production/demo hosts, discovery
pagination, snapshot subscription ordering, timestamps and units, delta shapes, sequence
semantics, reconnect/rate limits, actual asks versus opposite bids, collateral, payout, fee
schedule/version/rounding, order minimum/tick/quantity grids, supported order guarantees,
client-ID reconciliation, fill IDs, cancellation and late fills, balances and settlement.

Eligibility evidence and explicit live authorization remain separate gates. Do not infer
eligibility from timezone or direct a user to another host to bypass product restrictions.
