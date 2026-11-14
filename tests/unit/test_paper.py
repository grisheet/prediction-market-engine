from decimal import Decimal as D

from app.cli import paper_report
from app.domain.models import BookLevel
from app.execution.paper import PaperBroker, PaperOrder, ReplayEvent


def order(**kwargs):
    data = dict(
        order_id="o",
        venue="mock",
        market_id="synthetic-1",
        outcome="YES",
        signal_ms=0,
        quantity="20",
        price_cap="0.5",
        latency_ms=10,
    )
    data.update(kwargs)
    return PaperOrder(**data)


def test_uses_arrival_book(fixture):
    _, yes, _, fee = fixture
    worse = yes.model_copy(update={"asks": (BookLevel(price="0.7", quantity="20"),)})
    b = PaperBroker(
        [ReplayEvent(at_ms=0, book=yes, fee=fee), ReplayEvent(at_ms=5, book=worse, fee=fee)]
    )
    assert b.submit(order()).state == "REJECTED"


def test_partial_and_no_reuse(fixture):
    _, yes, _, fee = fixture
    b = PaperBroker([ReplayEvent(at_ms=0, book=yes, fee=fee)])
    first = b.submit(order(quantity="15"))
    assert first.filled_quantity == 15
    assert b.submit(order(quantity="15")) == first
    second = b.submit(order(order_id="second"))
    assert second.state == "PARTIAL"
    assert second.filled_quantity == 5
    assert b.submit(order(order_id="third")).state == "REJECTED"


def test_indeterminate_missing_and_fee_reject(fixture):
    assert PaperBroker([]).submit(order()).state == "INDETERMINATE"
    assert (
        PaperBroker([ReplayEvent(at_ms=0, book=fixture[1])]).submit(order()).reason
        == "UNKNOWN_FEES"
    )


def test_disconnection_and_stale(fixture):
    event = ReplayEvent(at_ms=0, book=fixture[1], fee=fixture[3], connected=False)
    assert PaperBroker([event]).submit(order()).state == "REJECTED"
    event = event.model_copy(update={"connected": True})
    assert PaperBroker([event], max_age_ms=1).submit(order()).state == "REJECTED"


def test_one_leg_failure(fixture):
    _, yes, no, fee = fixture
    broker = PaperBroker(
        [
            ReplayEvent(at_ms=0, book=yes, fee=fee),
            ReplayEvent(at_ms=0, book=no, fee=fee, market_open=False),
        ]
    )
    a = broker.submit(order())
    b = broker.submit(order(order_id="no", outcome="NO", price_cap="1"))
    assert a.filled_quantity == 20 and b.filled_quantity == 0
    assert a.cost + a.fee == D("9.30")


def test_deterministic_report():
    assert paper_report(42) == paper_report(42)
    assert D(paper_report()["potential_settlement_surplus_usd"]) == D("0.40")
    assert paper_report()["realized_trading_pnl_usd"] == "0"


def test_fee_change_at_arrival(fixture):
    _, yes, _, fee = fixture
    expensive = fee.model_copy(update={"per_contract": D("0.02")})
    broker = PaperBroker(
        [ReplayEvent(at_ms=0, book=yes, fee=fee), ReplayEvent(at_ms=5, book=yes, fee=expensive)]
    )
    assert broker.submit(order()).fee == D("0.40")


def test_new_snapshot_does_not_resurrect_consumed_size(fixture):
    _, yes, _, fee = fixture
    broker = PaperBroker(
        [
            ReplayEvent(at_ms=0, book=yes, fee=fee),
            ReplayEvent(at_ms=20, book=yes.model_copy(update={"version": "2"}), fee=fee),
        ]
    )
    assert broker.submit(order()).filled_quantity == 20
    assert broker.submit(order(order_id="later", signal_ms=25)).filled_quantity == 0


def test_out_of_order_arrivals_and_conflicting_order_ids(fixture):
    import pytest

    _, yes, _, fee = fixture
    broker = PaperBroker([ReplayEvent(at_ms=0, book=yes, fee=fee)])
    broker.submit(order(signal_ms=100))
    with pytest.raises(ValueError, match="arrival order"):
        broker.submit(order(order_id="old", signal_ms=0))
    with pytest.raises(ValueError, match="idempotency conflict"):
        broker.submit(order(signal_ms=100, quantity="1"))
