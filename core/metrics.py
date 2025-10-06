from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class Metrics(Protocol):
    def increment(self, name: str, tags: Mapping[str, str] | None = None) -> None: ...  # pragma: no cover - interface only

class _NoopMetrics:
    def increment(self, name: str, tags: Mapping[str, str] | None = None) -> None:  # pragma: no cover - noop
        return

_metrics: Metrics = _NoopMetrics()

def set_metrics(m: Metrics) -> None:
    global _metrics
    _metrics = m

def increment(name: str, tags: Mapping[str, str] | None = None) -> None:
    _metrics.increment(name, tags)
