# Fee and sizing model

All amounts are Decimal USD unless a typed field says quantity or probability-like price.
Price is USD per contract; payout is USD per matched contract. Non-USD markets reject until
a verified conversion and exposure model exists. Integer and fractional quantity increments
use their least common executable multiple, not a floating-point tolerance.

`FeeSchedule` is synthetic only. Each consumed ask level incurs:

```
raw = quantity * (per_contract + probability_coefficient * price * (1 - price))
fee = max(minimum_per_fill, ceil(raw / rounding_unit) * rounding_unit)
```

The probability coefficient assumes unit-payout prices. The default mock coefficient is zero.
This model does not claim to represent any real venue. Unknown schedules reject evaluation;
an explicit zero-fee schedule differs from a missing schedule. Fee-unit rounding always rounds
up; price and quantity grids reject invalid input rather than silently rounding order intent.

For q paired units, gross profit equals conservative payout minus walked acquisition costs.
Net subtracts actual modeled fees and the separately displayed adverse-movement reserve.
ROI divides net by acquisition cost plus fees plus reserve. No extra spread/slippage charge
repeats costs already included in the depth walk; no gas charge is invented.

Feasible q respects depth, both market minimums/increments, each leg's balance, shared-wallet
cash for a within-venue pair, each order limit, unmatched-leg budget, total remaining capacity
and event remaining capacity. A caller with existing commitments must supply remaining
capacity and must reserve/revalidate before any future execution. Pricing alone does not
reserve capital. All grid points are enumerated, including fee-rounding changes, up to the
configured ceiling. A positive optimum must pass both configured absolute and ROI thresholds.

The synthetic 20-unit case: 0.46 + 0.51 acquisition per unit, 0.005 fee per leg per unit,
USD 19.40 total acquisition, USD 0.20 fees, USD 20 payout, USD 0.40 net before reserves.
The default USD 5 unmatched budget and profit threshold deliberately prevent a paper entry
for this tiny synthetic edge. `demo` isolates arithmetic with explicit documented overrides.
Capital remains locked until settlement; potential surplus is not realized trading P&L.
