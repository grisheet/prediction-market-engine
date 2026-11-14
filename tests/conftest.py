from decimal import Decimal

import pytest

from app.config import Settings
from app.pricing.engine import evaluate
from app.venues.mock import MockVenue


@pytest.fixture
def fixture():
    return MockVenue().fixture()


@pytest.fixture
def settings():
    return Settings(
        adverse_movement_reserve_per_share_usd="0",
        max_order_cost_usd="20",
        max_unmatched_cost_usd="20",
    )


@pytest.fixture
def quote(fixture, settings):
    market, yes, no, fee = fixture

    def run(**overrides):
        args = dict(
            a=market,
            b=market,
            ba=yes,
            bb=no,
            fa=fee,
            fb=fee,
            settings=settings,
            now_ns=0,
            balances=(Decimal("50"), Decimal("50")),
        )
        args.update(overrides)
        return evaluate(**args)

    return run
