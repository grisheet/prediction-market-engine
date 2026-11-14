import asyncio
from decimal import Decimal

from app.domain.models import BookLevel, OrderBook, Quality


class BookState:
    """Synthetic sequence protocol only. Real feed bootstrap needs venue verification."""

    def __init__(self) -> None:
        self.book: OrderBook | None = None
        self.invalidations = 0

    def invalidate(self) -> None:
        self.invalidations += 1
        if self.book:
            self.book = self.book.model_copy(update={"quality": Quality.INVALID})

    def snapshot(self, book: OrderBook) -> None:
        if book.quality != Quality.VALID:
            raise ValueError("invalid snapshot")
        self.book = book

    def delta(
        self,
        *,
        market_id: str,
        outcome: str,
        version: str,
        sequence: int,
        price: Decimal,
        quantity: Decimal,
        received_ns: int,
    ) -> bool:
        b = self.book
        if b is None or b.quality != Quality.VALID:
            return False
        if (market_id, outcome, version) != (b.market_id, b.outcome, b.version):
            self.invalidate()
            return False
        if b.sequence is None or sequence != b.sequence + 1:
            self.invalidate()
            return False
        try:
            levels = {v.price: v.quantity for v in b.asks}
            if quantity < 0:
                raise ValueError("negative depth")
            if quantity == 0:
                levels.pop(price, None)
            else:
                levels[price] = quantity
            payload = b.model_dump()
            payload.update(
                asks=[BookLevel(price=p, quantity=q) for p, q in sorted(levels.items())],
                sequence=sequence,
                received_monotonic_ns=received_ns,
            )
            self.book = OrderBook.model_validate(payload)
            return True
        except ValueError:
            self.invalidate()
            return False


class BoundedFeed:
    def __init__(self, state: BookState, capacity: int = 100) -> None:
        self.queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=capacity)
        self.state = state
        self.overflows = 0

    def publish(self, event: dict[str, str]) -> bool:
        try:
            self.queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            self.overflows += 1
            self.state.invalidate()
            return False


def opposite_bids_to_asks(
    bids: tuple[BookLevel, ...], payout: Decimal, verified_complement: bool
) -> tuple[BookLevel, ...]:
    if not verified_complement:
        raise ValueError("documented complement semantics required")
    return tuple(BookLevel(price=payout - v.price, quantity=v.quantity) for v in bids)
