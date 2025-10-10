"""Lightweight application telemetry helpers.

Provides an optional OpenTelemetry counter ``yuplan.events_total`` capturing
domain-level events (e.g., registrering). Gracefully degrades to no-op when
OTEL SDK isn't installed so local/dev environments incur zero friction.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

try:  # pragma: no cover - optional dependency
    from opentelemetry.metrics import get_meter  # type: ignore
    _METER = get_meter("yuplan.app")
    _EVENTS = _METER.create_counter(
        name="yuplan.events_total",
        description="Domain events (labels: action, avdelning, maltid)",
    )
except Exception:  # pragma: no cover
    _METER = None
    _EVENTS = None

# Local in-process event counts (pilot visibility without backend)
LOCAL_EVENTS: Counter[str] = Counter()


def track_event(action: str, *, avdelning: str | None = None, maltid: str | None = None) -> None:
    """Record a domain event if metrics are available.

    Parameters
    ----------
    action: str
        The event action key (e.g., "registrering").
    avdelning: Optional[str]
        Unit/department label if relevant.
    maltid: Optional[str]
        Meal type label if relevant.
    """
    # Mirror to local counter irrespective of OTEL availability
    LOCAL_EVENTS[action] += 1
    if _EVENTS:
        labels: dict[str, Any] = {"action": action}
        if avdelning:
            labels["avdelning"] = avdelning
        if maltid:
            labels["maltid"] = maltid
        try:  # pragma: no cover - defensive against SDK misconfiguration
            _EVENTS.add(1, labels)  # type: ignore[arg-type]
        except Exception:
            pass


__all__ = ["track_event", "LOCAL_EVENTS"]
