from app.config import Settings
from app.venues.base import UnsupportedCapability


def require_live(settings: Settings) -> None:
    # Deliberately unconditional until M3-M6 acceptance, eligibility and authorization pass.
    raise UnsupportedCapability(
        "LIVE_DISABLED: adapters, eligibility, fee contracts, reconciliation and arming "
        "are not verified; configuration alone cannot authorize submission"
    )
