# Equivalence and approvals

A common title does not establish equivalent payouts. No automatic real-market approval or
LLM approval path exists. The library accepts typed human mapping records for offline research;
the authenticated dashboard approval workflow is not implemented.

Each approval binds ordered venue/market identities, exact rules hashes, canonical event,
approver, rationale, timestamp, selected leg outcomes and a material-scenario coverage matrix.
Each scenario stores the two selected legs' USD payouts per matched unit. The conservative
payout equals the minimum sum across scenarios. Empty coverage, changed hashes, revoked
status, identity mismatch or outcome-orientation mismatch prevents evaluation. Rules changes
invalidate use immediately; automatic persisted revocation remains future workflow work.

Approve A.YES + B.NO and A.NO + B.YES independently, with separate coverage matrices. The
strategy helper evaluates both. A matrix for one orientation cannot authorize the other.

Before approving real rules compare exact proposition, entities, observation window, cutoff,
timezone, measurement authority, early settlement, ties, rounding and revisions, postponement,
cancellation/refund, void behavior and dispute rules. Save raw text and provenance for each.
Reject unresolved ambiguity; scenario completeness requires human expertise and cannot be
established by checking matrix arithmetic alone. Cross-currency equivalence remains unsupported.
