from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.domain.models import BookLevel, OrderBook, Quality
from app.pricing.engine import common_grid, walk
from app.pricing.fees import FeeSchedule


def test_exact_spec_case(quote):
    r = quote()
    assert r.quantity == 20
    assert r.acquisition_cost == D("19.40")
    assert r.gross_profit == D("0.60")
    assert r.fees == D("0.20")
    assert r.net_profit == D("0.40")
    assert isinstance(r.model_dump(mode="json")["net_profit"], str)


@pytest.mark.parametrize("value", [0.1, True, "NaN", "Infinity", "-Infinity"])
def test_decimal_rejects_inexact_or_nonfinite(value):
    with pytest.raises((ValueError, ValidationError)):
        BookLevel(price=value, quantity="1")


def test_missing_fees_not_evaluable(quote):
    assert quote(fa=None).status == "NOT_EVALUABLE"


def test_stale_invalid_skew(quote, fixture):
    _, yes, no, _ = fixture
    assert quote(now_ns=1_000_000_001).rejection_reasons == ("STALE_BOOK",)
    assert quote(ba=yes.model_copy(update={"quality": Quality.INVALID})).status == "REJECTED"
    assert quote(
        bb=no.model_copy(update={"received_monotonic_ns": 600_000_000}), now_ns=600_000_000
    ).rejection_reasons == ("RECEIVE_SKEW",)
    assert quote(now_ns=-1).rejection_reasons == ("MONOTONIC_CLOCK_MISMATCH",)


def test_depth_walk_and_insufficient_depth(fixture):
    _, yes, _, fee = fixture
    b = yes.model_copy(
        update={
            "asks": (BookLevel(price="0.4", quantity="2"), BookLevel(price="0.6", quantity="3"))
        }
    )
    assert walk(b, D("4"), fee).cost == D("2.0")
    with pytest.raises(ValueError, match="INSUFFICIENT_DEPTH"):
        walk(b, D("6"), fee)


def test_common_grid():
    assert common_grid(D("0.3"), D("0.2")) == D("0.6")
    assert common_grid(D("1"), D("0.01")) == 1


def test_minimum_and_fee_rounding():
    f = FeeSchedule(
        version="test", per_contract="0.001", rounding_unit="0.05", minimum_per_fill="0.1"
    )
    assert f.fill_fee(D("0.4"), D("1")) == D("0.1")
    assert f.fill_fee(D("0.4"), D("151")) == D("0.20")
    assert f.fill_fee(D("0.4"), D("0")) == 0


def test_no_shared_wallet_double_spend(quote):
    r = quote(balances=(D("10"), D("10")))
    assert r.acquisition_cost + r.fees <= D("10")
    assert r.quantity < 20


def test_reserves_and_limits(quote, settings):
    r = quote(
        settings=settings.model_copy(update={"adverse_movement_reserve_per_share_usd": D("0.01")})
    )
    assert r.status == "REJECTED"  # Net 0.20 falls below the absolute 0.25 threshold.
    r = quote(available_total=D("1"))
    assert r.status == "REJECTED"


def test_currency_unknown_and_book_identity(quote, fixture):
    m, y, _, _ = fixture
    assert quote(a=m.model_copy(update={"currency": "USDC"})).status == "NOT_EVALUABLE"
    assert quote(ba=y.model_copy(update={"market_id": "other"})).status == "REJECTED"
    assert quote(ba=y.model_copy(update={"asks": ()})).status == "REJECTED"


def test_book_validates_order_and_cross(fixture):
    _, y, _, _ = fixture
    data = y.model_dump()
    data["bids"] = [dict(price="0.5", quantity="1")]
    with pytest.raises(ValidationError):
        OrderBook.model_validate(data)
    data = y.model_dump()
    data["asks"] = [dict(price="0.6", quantity="1"), dict(price="0.5", quantity="1")]
    with pytest.raises(ValidationError):
        OrderBook.model_validate(data)


def test_quantity_grid_and_search_guard(quote, fixture, settings):
    m, y, _, _ = fixture
    assert quote(a=m.model_copy(update={"quantity_increment": D("3")})).status == "NOT_EVALUABLE"
    assert (
        quote(settings=settings.model_copy(update={"max_sizing_steps": 2})).status
        == "NOT_EVALUABLE"
    )
    assert (
        quote(ba=y.model_copy(update={"asks": (BookLevel(price="0.461", quantity="20"),)})).status
        == "REJECTED"
    )


def test_default_unmatched_budget_blocks_signal(quote):
    from app.config import Settings

    assert quote(settings=Settings()).status == "REJECTED"


def test_invalid_decimal_string_is_validation_error():
    with pytest.raises(ValidationError):
        BookLevel(price="invalid", quantity="1")


def test_unknown_fee_model_for_non_unit_payout(quote, fixture):
    m, _, _, fee = fixture
    m = m.model_copy(update={"payout": D("2")})
    fee = fee.model_copy(update={"probability_coefficient": D("0.1")})
    assert quote(a=m, b=m, fa=fee).rejection_reasons == ("UNSUPPORTED_FEE_PAYOUT_MODEL",)
