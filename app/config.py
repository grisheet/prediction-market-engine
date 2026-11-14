from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.models import Nonnegative, Positive


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PM_", extra="forbid")
    mode: Literal["offline_demo", "replay", "live_paper", "kalshi_demo", "live"] = "offline_demo"
    live_trading_enabled: bool = False
    require_operator_arm: bool = True
    operator_arm_ttl_seconds: int = Field(default=900, gt=0)
    allow_cross_currency: bool = False
    require_approved_cross_venue_mapping: bool = True
    max_book_age_ms: int = Field(default=1000, gt=0)
    max_cross_venue_receive_skew_ms: int = Field(default=500, ge=0)
    min_net_profit_usd: Nonnegative = Decimal("0.25")
    min_net_roi: Nonnegative = Decimal("0.005")
    max_order_cost_usd: Positive = Decimal("10.00")
    max_total_committed_usd: Positive = Decimal("50.00")
    max_event_committed_usd: Positive = Decimal("20.00")
    max_unmatched_cost_usd: Nonnegative = Decimal("5.00")
    max_daily_realized_loss_usd: Positive = Decimal("5.00")
    adverse_movement_reserve_per_share_usd: Nonnegative = Decimal("0.005")
    max_sizing_steps: int = Field(default=100_000, gt=0)
    daily_reset_timezone: str = "UTC"
    database_url: str = "sqlite:///engine.db"
    control_token: str = ""

    @model_validator(mode="after")
    def gates(self) -> "Settings":
        if not self.require_operator_arm or self.allow_cross_currency:
            raise ValueError("unsupported unsafe configuration")
        if not self.require_approved_cross_venue_mapping:
            raise ValueError("mapping approval is mandatory")
        if self.daily_reset_timezone != "UTC":
            raise ValueError("only UTC daily reset is implemented")
        return self


def load_settings(path: str | None = None) -> Settings:
    data = yaml.safe_load(Path(path).read_text()) if path else {}
    # Environment overrides YAML intentionally, including empty control tokens.
    from os import environ
    from typing import Any

    values: dict[str, Any] = dict(data or {})
    for key in Settings.model_fields:
        if "PM_" + key.upper() in environ:
            values[key] = environ["PM_" + key.upper()]
    return Settings(**values)
