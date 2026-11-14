from app.domain.models import Model

TRANSITIONS: dict[str, frozenset[str]] = {
    "DETECTED": frozenset({"VALIDATING", "HALTED"}),
    "VALIDATING": frozenset({"RESERVED", "REJECTED", "HALTED"}),
    "RESERVED": frozenset({"SUBMITTING", "HALTED"}),
    "SUBMITTING": frozenset({"PARTIALLY_FILLED", "PAIRED", "REJECTED", "UNKNOWN"}),
    "PARTIALLY_FILLED": frozenset({"CANCEL_REQUESTED", "HEDGING", "UNWINDING", "MANUAL_REVIEW"}),
    "CANCEL_REQUESTED": frozenset({"CANCEL_CONFIRMED", "UNKNOWN", "PARTIALLY_FILLED", "PAIRED"}),
    "CANCEL_CONFIRMED": frozenset({"PARTIALLY_FILLED", "PAIRED", "MANUAL_REVIEW"}),
    "UNKNOWN": frozenset({"MANUAL_REVIEW", "PARTIALLY_FILLED", "PAIRED", "REJECTED"}),
    "HEDGING": frozenset({"PAIRED", "MANUAL_REVIEW", "UNKNOWN"}),
    "UNWINDING": frozenset({"SETTLEMENT_PENDING", "MANUAL_REVIEW", "UNKNOWN"}),
    "PAIRED": frozenset({"SETTLEMENT_PENDING"}),
    "SETTLEMENT_PENDING": frozenset({"SETTLED", "MANUAL_REVIEW"}),
    "HALTED": frozenset({"MANUAL_REVIEW"}),
    "MANUAL_REVIEW": frozenset(),
    "REJECTED": frozenset(),
    "SETTLED": frozenset(),
}


class ExecutionState(Model):
    state: str = "DETECTED"

    def advance(self, target: str) -> "ExecutionState":
        if target not in TRANSITIONS.get(self.state, frozenset()):
            raise ValueError(f"illegal transition {self.state} -> {target}")
        return ExecutionState(state=target)
