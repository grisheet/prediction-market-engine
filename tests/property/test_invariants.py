from decimal import Decimal as D

from hypothesis import given
from hypothesis import strategies as st

from app.config import Settings
from app.domain.models import BookLevel
from app.pricing.engine import evaluate
from app.pricing.fees import FeeSchedule
from app.venues.mock import MockVenue


@given(st.integers(1, 45), st.integers(1, 45), st.integers(1, 80))
def test_depth_and_risk_budgets(p1, p2, depth):
    market, yes, no, fee = MockVenue().fixture()
    yes = yes.model_copy(update={"asks": (BookLevel(price=D(p1) / 100, quantity=D(depth)),)})
    no = no.model_copy(update={"asks": (BookLevel(price=D(p2) / 100, quantity=D(depth)),)})
    cfg = Settings(min_net_profit_usd="0", min_net_roi="0")
    result = evaluate(market, market, yes, no, fee, fee, cfg, 0, (D("50"), D("50")))
    if result.status == "EVALUABLE":
        assert result.quantity <= depth
        assert (
            result.acquisition_cost + result.fees + result.other_costs
            <= cfg.max_event_committed_usd
        )
        assert all(leg.cost + leg.fee <= cfg.max_order_cost_usd for leg in result.legs)


@given(st.integers(0, 10), st.integers(0, 10))
def test_more_fees_never_improve_optimized_profit(base, extra):
    market, yes, no, _ = MockVenue().fixture()
    cfg = Settings(
        min_net_profit_usd="0",
        min_net_roi="0",
        adverse_movement_reserve_per_share_usd="0",
        max_order_cost_usd="20",
        max_unmatched_cost_usd="20",
    )

    def evaluate_fee(cents):
        fee = FeeSchedule(version="property", per_contract=D(cents) / 100)
        return evaluate(market, market, yes, no, fee, fee, cfg, 0, (D("50"), D("50")))

    assert evaluate_fee(base + extra).net_profit <= evaluate_fee(base).net_profit


@given(st.integers(0, 20))
def test_higher_acquisition_cost_never_improves_profit(extra):
    market, yes, no, fee = MockVenue().fixture()
    cfg = Settings(min_net_profit_usd="0", min_net_roi="0")
    base = evaluate(market, market, yes, no, fee, fee, cfg, 0, (D("50"), D("50")))
    worse = yes.model_copy(
        update={"asks": (BookLevel(price=D("0.46") + D(extra) / 100, quantity="20"),)}
    )
    result = evaluate(market, market, worse, no, fee, fee, cfg, 0, (D("50"), D("50")))
    assert result.net_profit <= base.net_profit


@given(st.integers(0, 10000), st.integers(0, 50))
def test_replay_identical_seed_data_and_config(seed, jitter):
    from app.execution.paper import PaperBroker, PaperOrder, ReplayEvent

    _, yes, no, fee = MockVenue().fixture()
    events = [ReplayEvent(at_ms=0, book=b, fee=fee) for b in (yes, no)]
    orders = [
        PaperOrder(
            order_id=str(i),
            venue="mock",
            market_id="synthetic-1",
            outcome="YES",
            signal_ms=i * 100,
            quantity="3",
            price_cap="1",
        )
        for i in range(4)
    ]

    def run():
        broker = PaperBroker(events, seed=seed, jitter_ms=jitter)
        return [broker.submit(order).model_dump_json() for order in orders]

    assert run() == run()


@given(st.lists(st.integers(1, 20), min_size=1, max_size=10))
def test_duplicate_fills_never_double_count(quantities):
    import tempfile
    from pathlib import Path

    from app.storage.database import Database

    with tempfile.TemporaryDirectory() as temp:
        db = Database("sqlite:///" + str(Path(temp) / "fills.db"))
        db.initialize()
        expected = D("0")
        for index, q in enumerate(quantities):
            args = (str(index), "mock", "m", "YES", D(q), D(q) / 2, D("0.01"))
            assert db.apply_fill(*args)
            assert not db.apply_fill(*args)
            expected += q
        assert D(db.positions()[0]["quantity"]) == expected
        db.engine.dispose()


@given(st.dictionaries(st.integers(1, 99), st.integers(0, 50), max_size=20))
def test_depth_updates_preserve_nonnegative_depth(updates):
    from app.books.manager import BookState

    _, yes, _, _ = MockVenue().fixture()
    state = BookState()
    state.snapshot(yes)
    for sequence, (cents, quantity) in enumerate(updates.items(), 2):
        assert state.delta(
            market_id=yes.market_id,
            outcome="YES",
            version="1",
            sequence=sequence,
            price=D(cents) / 100,
            quantity=D(quantity),
            received_ns=sequence,
        )
        assert all(level.quantity > 0 for level in state.book.asks)
