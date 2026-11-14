from decimal import ROUND_CEILING, Decimal

from app.domain.models import Model, Nonnegative, Positive


class FeeSchedule(Model):
    """Synthetic, per-consumed-level taker schedule. Never a venue fee claim."""

    version: str
    per_contract: Nonnegative
    probability_coefficient: Nonnegative = Decimal("0")
    rounding_unit: Positive = Decimal("0.01")
    minimum_per_fill: Nonnegative = Decimal("0")

    def fill_fee(self, price: Decimal, quantity: Decimal) -> Decimal:
        if not quantity.is_finite() or not price.is_finite() or quantity < 0 or price < 0:
            raise ValueError("invalid fee inputs")
        if self.probability_coefficient and price > 1:
            raise ValueError("probability fee model supports only unit payout prices")
        if quantity == 0:
            return Decimal("0")
        raw = quantity * (self.per_contract + self.probability_coefficient * price * (1 - price))
        return max(
            self.minimum_per_fill,
            (raw / self.rounding_unit).to_integral_value(rounding=ROUND_CEILING)
            * self.rounding_unit,
        )
