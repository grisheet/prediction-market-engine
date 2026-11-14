from collections.abc import AsyncIterator
from typing import Any

from app.domain.models import Model


class UnsupportedCapability(RuntimeError):
    pass


class Capabilities(Model):
    read_access: bool = False
    order_types: tuple[str, ...] = ()
    minimums_verified: bool = False
    sandbox_verified: bool = False
    sequence_support: bool = False
    fee_coverage: bool = False
    live_ready: bool = False


class Venue:
    capabilities = Capabilities()

    async def discover_markets(self) -> list[dict[str, Any]]:
        raise UnsupportedCapability("discovery UNVERIFIED")

    async def fetch_market_rules(self, market_id: str) -> str:
        raise UnsupportedCapability("rules UNVERIFIED")

    async def fetch_order_book(self, market_id: str, outcome: str) -> dict[str, Any]:
        raise UnsupportedCapability("book UNVERIFIED")

    async def subscribe_books(self) -> AsyncIterator[dict[str, Any]]:
        raise UnsupportedCapability("subscription UNVERIFIED")
        yield {}  # Makes the interface an async iterator; unreachable by design.

    async def fetch_fee_schedule(self) -> dict[str, Any]:
        raise UnsupportedCapability("fees UNVERIFIED")

    async def get_balances(self) -> dict[str, str]:
        raise UnsupportedCapability("balances UNVERIFIED")

    async def place_order(self, intent: dict[str, Any]) -> dict[str, Any]:
        raise UnsupportedCapability("LIVE SUBMISSION DISABLED")

    async def cancel_order(self, order_id: str) -> None:
        raise UnsupportedCapability("cancel UNVERIFIED")

    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        raise UnsupportedCapability("order reconciliation UNVERIFIED")

    async def fetch_fills(self) -> list[dict[str, Any]]:
        raise UnsupportedCapability("fills UNVERIFIED")

    async def fetch_positions(self) -> list[dict[str, Any]]:
        raise UnsupportedCapability("positions UNVERIFIED")
