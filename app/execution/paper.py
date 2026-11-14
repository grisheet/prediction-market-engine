import random
from decimal import Decimal
from typing import Literal

from app.domain.models import BookLevel, Model, Nonnegative, OrderBook, Positive, Quality
from app.pricing.engine import walk
from app.pricing.fees import FeeSchedule


class ReplayEvent(Model):
    at_ms: int
    book: OrderBook | None = None
    fee: FeeSchedule | None = None
    connected: bool = True
    market_open: bool = True


class PaperOrder(Model):
    order_id: str
    venue: str
    market_id: str
    outcome: str
    signal_ms: int
    quantity: Positive
    price_cap: Nonnegative
    latency_ms: int = 10


class PaperResult(Model):
    order_id: str
    state: Literal["FILLED", "PARTIAL", "REJECTED", "INDETERMINATE"]
    filled_quantity: Nonnegative = Decimal("0")
    cost: Nonnegative = Decimal("0")
    fee: Nonnegative = Decimal("0")
    arrival_ms: int
    reason: str = ""
    result_label: str = "SYNTHETIC"


class PaperBroker:
    """Aggressive buy orders only; exact seeded latency and conservative depletion."""

    def __init__(
        self, events: list[ReplayEvent], seed: int = 42, jitter_ms: int = 0, max_age_ms: int = 1000
    ) -> None:
        if jitter_ms < 0 or max_age_ms < 0:
            raise ValueError("invalid latency/freshness")
        if any(e.at_ms < 0 for e in events):
            raise ValueError("negative replay time")
        if [e.at_ms for e in events] != sorted(e.at_ms for e in events):
            raise ValueError("replay events must be ordered")
        self.events = events
        self.rng = random.Random(seed)
        self.jitter_ms = jitter_ms
        self.max_age_ms = max_age_ms
        self.used: dict[tuple[str, str, str, Decimal], Decimal] = {}
        self.results: dict[str, tuple[PaperOrder, PaperResult]] = {}
        self.last_arrival = -1

    def submit(self, order: PaperOrder) -> PaperResult:
        if order.order_id in self.results:
            original, result = self.results[order.order_id]
            if original != order:
                raise ValueError("order idempotency conflict")
            return result
        if order.signal_ms < 0 or order.latency_ms < 0:
            raise ValueError("negative replay latency")
        arrival = order.signal_ms + order.latency_ms + self.rng.randint(0, self.jitter_ms)
        if arrival < self.last_arrival:
            raise ValueError("orders must be processed in arrival order")
        self.last_arrival = arrival
        candidates = [
            e
            for e in self.events
            if e.at_ms <= arrival
            and (
                e.book is None
                or (e.book.venue, e.book.market_id, e.book.outcome)
                == (order.venue, order.market_id, order.outcome)
            )
        ]
        event = candidates[-1] if candidates else None
        state: Literal["FILLED", "PARTIAL", "REJECTED", "INDETERMINATE"]
        state, reason = "INDETERMINATE", "NO_ARRIVAL_DEPTH"
        quantity = cost = fee = Decimal("0")
        if event and event.book:
            b = event.book
            if (
                not event.connected
                or not event.market_open
                or b.quality != Quality.VALID
                or arrival - event.at_ms > self.max_age_ms
            ):
                state, reason = "REJECTED", "UNUSABLE_ARRIVAL_BOOK"
            elif event.fee is None:
                state, reason = "REJECTED", "UNKNOWN_FEES"
            else:
                levels = []
                for level in b.asks:
                    key = (b.venue, b.market_id, b.outcome, level.price)
                    left = max(Decimal("0"), level.quantity - self.used.get(key, Decimal("0")))
                    if left and level.price <= order.price_cap:
                        levels.append(BookLevel(price=level.price, quantity=left))
                available = sum((v.quantity for v in levels), Decimal("0"))
                quantity = min(order.quantity, available)
                if quantity:
                    quote = walk(b.model_copy(update={"asks": tuple(levels)}), quantity, event.fee)
                    cost, fee = quote.cost, quote.fee
                    state = "FILLED" if quantity == order.quantity else "PARTIAL"
                    reason = "" if state == "FILLED" else "INSUFFICIENT_ARRIVAL_DEPTH"
                    left = quantity
                    for level in levels:
                        take = min(left, level.quantity)
                        key = (b.venue, b.market_id, b.outcome, level.price)
                        self.used[key] = self.used.get(key, Decimal("0")) + take
                        left -= take
                        if not left:
                            break
                else:
                    state, reason = "REJECTED", "NO_EXECUTABLE_LIQUIDITY"
        result = PaperResult(
            order_id=order.order_id,
            state=state,
            filled_quantity=quantity,
            cost=cost,
            fee=fee,
            arrival_ms=arrival,
            reason=reason,
        )
        self.results[order.order_id] = (order, result)
        return result


class ReplayRecording(Model):
    schema_version: Literal[1] = 1
    result_label: Literal["SYNTHETIC"]
    events: tuple[ReplayEvent, ...]
    orders: tuple[PaperOrder, ...]
