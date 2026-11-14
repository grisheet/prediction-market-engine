import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.domain.models import utcnow


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    schema_version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))


class SystemState(Base):
    __tablename__ = "system_state"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Reservation(Base):
    __tablename__ = "reservations"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(200), index=True)
    amount: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(default=True)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_engine(
            url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
        )

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            if self.engine.dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            else:
                # PostgreSQL concurrency semantics are intentionally unverified.
                raise RuntimeError("transaction backend not validated; SQLite required")
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    def append(self, kind: str, key: str, payload: dict[str, Any]) -> None:
        with self.transaction() as session:
            session.add(
                Record(kind=kind, key=key, payload=payload, created_at=utcnow().isoformat())
            )

    def records(self, kind: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            return [
                r.payload
                for r in session.scalars(
                    select(Record).where(Record.kind == kind).order_by(Record.id)
                )
            ]

    def killed(self) -> bool:
        with Session(self.engine) as session:
            state = session.get(SystemState, "kill")
            return state is not None and state.value == "true"

    def activate_kill(self, actor: str) -> None:
        with self.transaction() as session:
            state = session.get(SystemState, "kill")
            if state is None:
                session.add(SystemState(key="kill", value="true"))
            else:
                state.value = "true"
            session.add(
                Record(
                    kind="audit",
                    key="kill:" + utcnow().isoformat(),
                    created_at=utcnow().isoformat(),
                    payload={
                        "action": "kill",
                        "actor": actor,
                        "effect": "new paper submissions blocked; no live orders exist",
                    },
                )
            )

    def reserve(
        self, key: str, event_id: str, amount: Decimal, total_limit: Decimal, event_limit: Decimal
    ) -> None:
        if not amount.is_finite() or amount <= 0:
            raise ValueError("reservation must be finite and positive")
        with self.transaction() as session:
            state = session.get(SystemState, "kill")
            if state and state.value == "true":
                raise ValueError("KILL_SWITCH")
            existing = session.get(Reservation, key)
            if existing:
                if (existing.event_id, Decimal(existing.amount), existing.active) != (
                    event_id,
                    amount,
                    True,
                ):
                    raise ValueError("reservation idempotency conflict")
                return
            active = list(session.scalars(select(Reservation).where(Reservation.active.is_(True))))
            total = sum((Decimal(r.amount) for r in active), Decimal("0"))
            event = sum((Decimal(r.amount) for r in active if r.event_id == event_id), Decimal("0"))
            if total + amount > total_limit or event + amount > event_limit:
                raise ValueError("RESERVATION_LIMIT")
            session.add(Reservation(key=key, event_id=event_id, amount=str(amount)))

    def release(self, key: str, reconciled: bool) -> None:
        if not reconciled:
            raise ValueError("reconciliation required")
        with self.transaction() as session:
            reservation = session.get(Reservation, key)
            if reservation is None:
                raise ValueError("unknown reservation")
            reservation.active = False

    def apply_fill(
        self,
        fill_id: str,
        venue: str,
        market: str,
        outcome: str,
        quantity: Decimal,
        cost: Decimal,
        fee: Decimal,
    ) -> bool:
        if any(not v.is_finite() or v < 0 for v in (quantity, cost, fee)) or quantity == 0:
            raise ValueError("invalid fill")
        payload = {
            "venue": venue,
            "market": market,
            "outcome": outcome,
            "quantity": str(quantity),
            "cost": str(cost),
            "fee": str(fee),
        }
        key = "fill:" + venue + ":" + fill_id
        with self.transaction() as session:
            existing = session.scalar(select(Record).where(Record.key == key))
            if existing:
                if existing.payload != payload:
                    raise ValueError("conflicting duplicate fill")
                return False
            stamp = utcnow().isoformat()
            session.add(Record(kind="fill", key=key, payload=payload, created_at=stamp))
            session.add(
                Record(
                    kind="cash_ledger",
                    key="cash:" + key,
                    payload={"currency": "USD", "delta": str(-cost - fee), "fill_key": key},
                    created_at=stamp,
                )
            )
            return True

    def positions(self) -> list[dict[str, str]]:
        positions: dict[tuple[str, str, str], Decimal] = {}
        for fill in self.records("fill"):
            key = (fill["venue"], fill["market"], fill["outcome"])
            positions[key] = positions.get(key, Decimal("0")) + Decimal(fill["quantity"])
        return [
            dict(venue=k[0], market=k[1], outcome=k[2], quantity=str(v))
            for k, v in sorted(positions.items())
        ]


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
