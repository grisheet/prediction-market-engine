from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def decimal_input(v: Any) -> Decimal:
    if isinstance(v, (float, bool)):
        raise ValueError("financial values must be Decimal, integer, or decimal strings")
    try:
        d = Decimal(v)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid decimal input") from exc
    if not d.is_finite():
        raise ValueError("financial values must be finite")
    return d


Money = Annotated[Decimal, BeforeValidator(decimal_input)]
Positive = Annotated[Money, Field(gt=0)]
Nonnegative = Annotated[Money, Field(ge=0)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Quality(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class Market(Model):
    venue: str
    environment: str = "synthetic"
    product: str = "binary"
    market_id: str
    event_id: str
    outcome_ids: tuple[str, str] = ("YES", "NO")
    title: str
    rules_text: str
    rules_hash: str
    source_url: str
    category: str = "synthetic"
    currency: str = "USD"
    payout: Positive = Decimal("1")
    close_time: datetime
    expected_resolution_time: datetime
    status: str = "OPEN"
    minimum_quantity: Positive = Decimal("1")
    quantity_increment: Positive = Decimal("1")
    tick_size: Positive = Decimal("0.01")
    fee_metadata: dict[str, str] = Field(default_factory=dict)
    last_verification_time: datetime


class BookLevel(Model):
    price: Nonnegative
    quantity: Positive


class OrderBook(Model):
    venue: str
    market_id: str
    outcome: Literal["YES", "NO"]
    bids: tuple[BookLevel, ...] = ()
    asks: tuple[BookLevel, ...] = ()
    version: str
    sequence: int | None = None
    venue_timestamp: datetime
    received_at: datetime
    received_monotonic_ns: int = Field(ge=0)
    quality: Quality = Quality.VALID

    @model_validator(mode="after")
    def structure(self) -> "OrderBook":
        for levels, reverse in ((self.bids, True), (self.asks, False)):
            prices = [level.price for level in levels]
            if prices != sorted(set(prices), reverse=reverse):
                raise ValueError("levels must be unique and ordered")
        if self.bids and self.asks and self.bids[0].price >= self.asks[0].price:
            raise ValueError("crossed or locked book")
        for stamp in (self.venue_timestamp, self.received_at):
            if stamp.tzinfo is None:
                raise ValueError("timestamps must be timezone aware")
        return self


class CanonicalEvent(Model):
    proposition: str
    entities: tuple[str, ...]
    measurement_source: str
    observation_window: str
    timezone: str
    cutoff: str
    resolution_criteria: str
    cancellation_rules: str
    dispute_provisions: str


class MappingApproval(Model):
    market_keys: tuple[str, str]
    rules_hashes: tuple[str, str]
    canonical_event: CanonicalEvent
    rationale: str
    leg_outcomes: tuple[Literal["YES", "NO"], Literal["YES", "NO"]] = ("YES", "NO")
    coverage: dict[str, tuple[Nonnegative, Nonnegative]]
    approved_at: datetime
    approver: str
    status: Literal["ACTIVE", "REVOKED"] = "ACTIVE"

    def valid_for(self, a: Market, b: Market) -> bool:
        return (
            self.status == "ACTIVE"
            and bool(self.coverage)
            and self.market_keys == (f"{a.venue}:{a.market_id}", f"{b.venue}:{b.market_id}")
            and self.rules_hashes == (a.rules_hash, b.rules_hash)
        )


class LegQuote(Model):
    venue: str
    market_id: str
    outcome: str
    quantity: Nonnegative
    cost: Nonnegative
    fee: Nonnegative
    worst_price: Nonnegative


class Opportunity(Model):
    status: Literal["EVALUABLE", "REJECTED", "NOT_EVALUABLE"]
    strategy: str
    legs: tuple[LegQuote, ...] = ()
    quantity: Nonnegative = Decimal("0")
    payout: Nonnegative = Decimal("0")
    acquisition_cost: Nonnegative = Decimal("0")
    fees: Nonnegative = Decimal("0")
    other_costs: Nonnegative = Decimal("0")
    gross_profit: Money = Decimal("0")
    net_profit: Money = Decimal("0")
    roi: Money = Decimal("0")
    receive_skew_ms: Nonnegative = Decimal("0")
    age_ms: Nonnegative = Decimal("0")
    rejection_reasons: tuple[str, ...] = ()
    expires_at: datetime | None = None
    result_label: str = "SYNTHETIC"


def utcnow() -> datetime:
    return datetime.now(UTC)
