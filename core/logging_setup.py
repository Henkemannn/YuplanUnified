"""Support log ring buffer for /admin/support.

Captures WARN+ log records with associated request_id (if request context) into
an in-memory deque for quick troubleshooting without external log aggregation.
"""

from __future__ import annotations

import collections
import logging
import time

from flask import g, has_request_context, request

LOG_BUFFER: collections.deque[dict] = collections.deque(maxlen=500)


class SupportLogHandler(logging.Handler):  # pragma: no cover - simple container
    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            rid = getattr(g, "request_id", "-") if has_request_context() else "-"
            path = request.path if has_request_context() else "-"
        except Exception:
            rid = "-"
            path = "-"
        LOG_BUFFER.append(
            {
                "ts": time.time(),
                "level": record.levelname,
                "msg": self.format(record),
                "request_id": rid,
                "path": path,
            }
        )


def install_support_log_handler() -> None:
    root = logging.getLogger()
    # Avoid duplicate attachment if reloaded
    if any(isinstance(h, SupportLogHandler) for h in root.handlers):
        return
    h = SupportLogHandler(level=logging.WARNING)
    h.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(h)


__all__ = ["LOG_BUFFER", "install_support_log_handler"]
