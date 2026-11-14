from decimal import Decimal

from app.config import Settings
from app.domain.models import MappingApproval, Market, Opportunity, OrderBook
from app.pricing.engine import evaluate
from app.pricing.fees import FeeSchedule


def cross_directions(
    a: Market,
    b: Market,
    a_yes: OrderBook,
    a_no: OrderBook,
    b_yes: OrderBook,
    b_no: OrderBook,
    fee_a: FeeSchedule | None,
    fee_b: FeeSchedule | None,
    settings: Settings,
    now_ns: int,
    balances: tuple[Decimal, Decimal],
    yes_no_approval: MappingApproval | None = None,
    no_yes_approval: MappingApproval | None = None,
) -> tuple[Opportunity, Opportunity]:
    """Coverage matrices are orientation specific. Both require independent approval."""
    return (
        evaluate(
            a, b, a_yes, b_no, fee_a, fee_b, settings, now_ns, balances, mapping=yes_no_approval
        ),
        evaluate(
            a, b, a_no, b_yes, fee_a, fee_b, settings, now_ns, balances, mapping=no_yes_approval
        ),
    )
