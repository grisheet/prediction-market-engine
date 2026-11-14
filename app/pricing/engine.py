from datetime import timedelta
from decimal import Decimal
from math import lcm
from typing import cast

from app.config import Settings
from app.domain.models import (
    LegQuote,
    MappingApproval,
    Market,
    Opportunity,
    OrderBook,
    Quality,
)
from app.pricing.fees import FeeSchedule

ZERO = Decimal("0")


def common_grid(a: Decimal, b: Decimal) -> Decimal:
    scale = Decimal(10) ** max(
        0, -cast(int, a.as_tuple().exponent), -cast(int, b.as_tuple().exponent)
    )
    return Decimal(lcm(int(a * scale), int(b * scale))) / scale


def walk(book: OrderBook, quantity: Decimal, schedule: FeeSchedule) -> LegQuote:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    remaining, cost, fee, worst = quantity, ZERO, ZERO, ZERO
    for level in book.asks:
        take = min(remaining, level.quantity)
        cost += take * level.price
        fee += schedule.fill_fee(level.price, take)
        worst = level.price
        remaining -= take
        if remaining == 0:
            return LegQuote(
                venue=book.venue,
                market_id=book.market_id,
                outcome=book.outcome,
                quantity=quantity,
                cost=cost,
                fee=fee,
                worst_price=worst,
            )
    raise ValueError("INSUFFICIENT_DEPTH")


def evaluate(
    a: Market,
    b: Market,
    ba: OrderBook,
    bb: OrderBook,
    fa: FeeSchedule | None,
    fb: FeeSchedule | None,
    settings: Settings,
    now_ns: int,
    balances: tuple[Decimal, Decimal],
    mapping: MappingApproval | None = None,
    available_total: Decimal | None = None,
    available_event: Decimal | None = None,
) -> Opportunity:
    cross = a.venue != b.venue
    strategy = "cross_venue" if cross else "within_venue"

    def reject(reason: str, unknown: bool = False) -> Opportunity:
        return Opportunity(
            status="NOT_EVALUABLE" if unknown else "REJECTED",
            strategy=strategy,
            rejection_reasons=(reason,),
        )

    if fa is None or fb is None:
        return reject("UNKNOWN_FEES", True)
    if fa.probability_coefficient and a.payout != 1 or fb.probability_coefficient and b.payout != 1:
        return reject("UNSUPPORTED_FEE_PAYOUT_MODEL", True)
    if a.currency != "USD" or b.currency != "USD":
        return reject("UNSUPPORTED_CURRENCY", True)
    if ba.outcome == bb.outcome:
        return reject("OUTCOMES_NOT_COMPLEMENTARY")
    if (ba.venue, ba.market_id) != (a.venue, a.market_id) or (bb.venue, bb.market_id) != (
        b.venue,
        b.market_id,
    ):
        return reject("BOOK_IDENTITY_MISMATCH")
    if a.status != "OPEN" or b.status != "OPEN":
        return reject("MARKET_CLOSED")
    if not cross and (a != b):
        return reject("UNPROVEN_WITHIN_VENUE_COVERAGE", True)
    payout_per_unit = a.payout
    if cross:
        if mapping is None or not mapping.valid_for(a, b):
            return reject("UNAPPROVED_OR_CHANGED_RULES")
        # Coverage amounts are per unit of the selected YES/NO orientation.
        if (ba.outcome, bb.outcome) != mapping.leg_outcomes:
            return reject("COVERAGE_ORIENTATION_MISMATCH")
        payout_per_unit = min(sum(v, ZERO) for v in mapping.coverage.values())
    if payout_per_unit <= 0:
        return reject("UNKNOWN_PAYOUT_COVERAGE", True)
    ages = [Decimal(now_ns - bk.received_monotonic_ns) / 1_000_000 for bk in (ba, bb)]
    if any(age < 0 for age in ages):
        return reject("MONOTONIC_CLOCK_MISMATCH")
    age = max(ages)
    skew = Decimal(abs(ba.received_monotonic_ns - bb.received_monotonic_ns)) / 1_000_000
    if any(bk.quality != Quality.VALID for bk in (ba, bb)):
        return reject("INVALID_BOOK")
    if age > settings.max_book_age_ms:
        return reject("STALE_BOOK")
    if skew > settings.max_cross_venue_receive_skew_ms:
        return reject("RECEIVE_SKEW")
    for market, book in ((a, ba), (b, bb)):
        if any(
            level.price > market.payout
            or level.price % market.tick_size
            or level.quantity % market.quantity_increment
            for level in book.asks
        ):
            return reject("INVALID_VENUE_GRID")
    grid = common_grid(a.quantity_increment, b.quantity_increment)
    depth = min(sum((v.quantity for v in ba.asks), ZERO), sum((v.quantity for v in bb.asks), ZERO))
    if depth < max(a.minimum_quantity, b.minimum_quantity):
        return reject("INSUFFICIENT_DEPTH")
    steps = int(depth // grid)
    if steps > settings.max_sizing_steps:
        return reject("SIZING_GRID_LIMIT", True)
    total_cap = min(
        settings.max_total_committed_usd,
        available_total if available_total is not None else settings.max_total_committed_usd,
    )
    event_cap = min(
        settings.max_event_committed_usd,
        available_event if available_event is not None else settings.max_event_committed_usd,
    )
    best: Opportunity | None = None
    for i in range(1, steps + 1):
        q = grid * i
        if q < max(a.minimum_quantity, b.minimum_quantity):
            continue
        la, lb = walk(ba, q, fa), walk(bb, q, fb)
        reserve = q * settings.adverse_movement_reserve_per_share_usd
        spent = la.cost + lb.cost + la.fee + lb.fee + reserve
        if (
            la.cost + la.fee
            > min(balances[0], settings.max_order_cost_usd, settings.max_unmatched_cost_usd)
            or lb.cost + lb.fee
            > min(balances[1], settings.max_order_cost_usd, settings.max_unmatched_cost_usd)
            or spent > min(total_cap, event_cap)
        ):
            continue
        # A single shared venue wallet cannot spend the same cash twice.
        if not cross and spent > min(balances):
            continue
        gross = q * payout_per_unit - la.cost - lb.cost
        net = gross - la.fee - lb.fee - reserve
        roi = net / spent if spent else ZERO
        if net < settings.min_net_profit_usd or roi < settings.min_net_roi:
            continue
        candidate = Opportunity(
            status="EVALUABLE",
            strategy=strategy,
            legs=(la, lb),
            quantity=q,
            payout=q * payout_per_unit,
            acquisition_cost=la.cost + lb.cost,
            fees=la.fee + lb.fee,
            other_costs=reserve,
            gross_profit=gross,
            net_profit=net,
            roi=roi,
            receive_skew_ms=skew,
            age_ms=age,
            expires_at=min(ba.received_at, bb.received_at)
            + timedelta(milliseconds=settings.max_book_age_ms),
        )
        if best is None or candidate.net_profit > best.net_profit:
            best = candidate
    return best if best is not None else reject("NO_FEASIBLE_PROFITABLE_SIZE")
