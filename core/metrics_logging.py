from __future__ import annotations

import logging
from collections.abc import Mapping

from .metrics import Metrics

logger = logging.getLogger("metrics")


class LoggingMetrics(Metrics):
    def increment(
        self, name: str, tags: Mapping[str, str] | None = None
    ) -> None:  # pragma: no cover - trivial
        ordered = dict(sorted((tags or {}).items()))
        # Structured-ish log for easy grep/ingest later
        logger.info("metric name=%s tags=%s", name, ordered)
