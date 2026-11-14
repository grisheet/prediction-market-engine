import json
import logging
from enum import StrEnum


class Event(StrEnum):
    STARTUP = "startup"
    BOOK_INVALID = "book_invalid"
    QUEUE_OVERFLOW = "queue_overflow"
    KILL_ACTIVATED = "kill_activated"


def emit(event: Event, count: int = 1) -> None:
    """Fixed event codes and counts only. Never accept raw payloads or credentials."""
    if not isinstance(event, Event) or count < 0:
        raise ValueError("invalid telemetry event")
    logging.getLogger("pm_engine").info(json.dumps({"event": event.value, "count": count}))
