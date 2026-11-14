from app.domain.models import CanonicalEvent, MappingApproval, utcnow


def approval(a, b):
    return MappingApproval(
        market_keys=(f"{a.venue}:{a.market_id}", f"{b.venue}:{b.market_id}"),
        rules_hashes=(a.rules_hash, b.rules_hash),
        canonical_event=CanonicalEvent(
            proposition="synthetic",
            entities=(),
            measurement_source="test",
            observation_window="test",
            timezone="UTC",
            cutoff="test",
            resolution_criteria="test",
            cancellation_rules="no cancellation",
            dispute_provisions="no dispute",
        ),
        rationale="Synthetic exhaustive YES/NO example",
        coverage={"yes": ("1", "0"), "no": ("0", "1")},
        approved_at=utcnow(),
        approver="unit-test",
    )


def test_approval_and_rule_changes(quote, fixture):
    a, _, no, _ = fixture
    b = a.model_copy(update={"venue": "other"})
    bb = no.model_copy(update={"venue": "other"})
    assert quote(b=b, bb=bb).rejection_reasons == ("UNAPPROVED_OR_CHANGED_RULES",)
    mapping = approval(a, b)
    assert quote(b=b, bb=bb, mapping=mapping).status == "EVALUABLE"
    assert (
        quote(b=b.model_copy(update={"rules_hash": "changed"}), bb=bb, mapping=mapping).status
        == "REJECTED"
    )
    revoked = mapping.model_copy(update={"status": "REVOKED"})
    assert quote(b=b, bb=bb, mapping=revoked).status == "REJECTED"


def test_void_coverage_cannot_create_edge(quote, fixture):
    a, _, no, _ = fixture
    b = a.model_copy(update={"venue": "other"})
    mapping = approval(a, b).model_copy(update={"coverage": {"void": (0, 0)}})
    assert (
        quote(b=b, bb=no.model_copy(update={"venue": "other"}), mapping=mapping).status
        == "NOT_EVALUABLE"
    )
