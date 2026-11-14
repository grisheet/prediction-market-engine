import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from app.domain.models import BookLevel, Market, OrderBook
from app.pricing.fees import FeeSchedule
from app.venues.base import Capabilities, Venue


class MockVenue(Venue):
    capabilities = Capabilities(read_access=True, fee_coverage=True, sequence_support=True)

    def fixture(self) -> tuple[Market, OrderBook, OrderBook, FeeSchedule]:
        stamp = datetime(2026, 1, 1, tzinfo=UTC)
        rules = "SYNTHETIC: YES or NO pays one USD; no void scenarios."
        market = Market(
            venue="mock",
            market_id="synthetic-1",
            event_id="synthetic-event",
            title="SYNTHETIC binary fixture",
            rules_text=rules,
            rules_hash=hashlib.sha256(rules.encode()).hexdigest(),
            source_url="synthetic://1",
            close_time=stamp + timedelta(days=1),
            expected_resolution_time=stamp + timedelta(days=2),
            last_verification_time=stamp,
        )
        outcomes: tuple[tuple[Literal["YES", "NO"], str], ...] = (("YES", "0.46"), ("NO", "0.51"))
        books = [
            OrderBook(
                venue="mock",
                market_id=market.market_id,
                outcome=outcome,
                asks=(BookLevel(price=Decimal(price), quantity=Decimal("20")),),
                version="1",
                sequence=1,
                venue_timestamp=stamp,
                received_at=stamp,
                received_monotonic_ns=0,
            )
            for outcome, price in outcomes
        ]
        return (
            market,
            books[0],
            books[1],
            FeeSchedule(version="synthetic-v1", per_contract=Decimal("0.005")),
        )

    async def discover_markets(self) -> list[dict[str, object]]:
        return [self.fixture()[0].model_dump(mode="json")]

    async def fetch_market_rules(self, market_id: str) -> str:
        if market_id != "synthetic-1":
            raise ValueError("unknown synthetic market")
        return self.fixture()[0].rules_text
