from decimal import Decimal as D

import pytest

from app.books.manager import BookState, BoundedFeed, opposite_bids_to_asks
from app.domain.models import BookLevel, Quality


def test_sequence_gap_and_resnapshot(fixture):
    _, yes, _, _ = fixture
    s = BookState()
    s.snapshot(yes)
    kwargs = dict(
        market_id=yes.market_id,
        outcome="YES",
        version="1",
        price=D("0.46"),
        quantity=D("10"),
        received_ns=1,
    )
    assert s.delta(sequence=2, **kwargs)
    assert not s.delta(sequence=4, **kwargs)
    assert s.book.quality == Quality.INVALID
    assert not s.delta(sequence=3, **kwargs)
    s.snapshot(yes)
    assert s.delta(sequence=2, **kwargs)


def test_overflow_invalidates(fixture):
    s = BookState()
    s.snapshot(fixture[1])
    feed = BoundedFeed(s, 1)
    assert feed.publish({"sequence": "2"})
    assert not feed.publish({"sequence": "3"})
    assert feed.overflows == 1
    assert s.book.quality == Quality.INVALID


def test_opposite_bid_requires_verified_semantics():
    bids = (BookLevel(price="0.54", quantity="20"),)
    with pytest.raises(ValueError):
        opposite_bids_to_asks(bids, D("1"), False)
    ask = opposite_bids_to_asks(bids, D("1"), True)[0]
    assert (ask.price, ask.quantity) == (D("0.46"), D("20"))
