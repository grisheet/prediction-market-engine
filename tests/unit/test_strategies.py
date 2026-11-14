from decimal import Decimal as D

from app.domain.models import CanonicalEvent, MappingApproval, utcnow
from app.strategies.paired import cross_directions


def test_both_cross_directions(fixture, settings):
    a, ay, an, fee = fixture
    b = a.model_copy(update={"venue": "other"})
    by, bn = (book.model_copy(update={"venue": "other"}) for book in (ay, an))
    canonical = CanonicalEvent(
        proposition="test",
        entities=(),
        measurement_source="test",
        observation_window="test",
        timezone="UTC",
        cutoff="test",
        resolution_criteria="test",
        cancellation_rules="none",
        dispute_provisions="none",
    )
    approval = MappingApproval(
        market_keys=("mock:synthetic-1", "other:synthetic-1"),
        rules_hashes=(a.rules_hash, b.rules_hash),
        canonical_event=canonical,
        rationale="synthetic exhaustive coverage",
        coverage={"yes": ("1", "0"), "no": ("0", "1")},
        approved_at=utcnow(),
        approver="test",
    )
    reverse = approval.model_copy(update={"leg_outcomes": ("NO", "YES")})
    result = cross_directions(
        a, b, ay, an, by, bn, fee, fee, settings, 0, (D("50"), D("50")), approval, reverse
    )
    assert all(r.status == "EVALUABLE" for r in result)
    assert [r.legs[0].outcome for r in result] == ["YES", "NO"]
