"""Lightweight audit event recorder for security-sensitive actions.

Currently stores events in an in-memory list (process local) and optionally emits
OpenTelemetry spans if OTEL is available. This is intentionally minimal; future
iterations can persist to DB or external sink.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

try:  # optional
    from opentelemetry import trace  # optional import
except Exception:  # pragma: no cover
    trace = None

_AUDIT_BUFFER: list[dict[str, Any]] = []
_MAX_BUFFER = 500

@dataclass
class AuditEvent:
    ts: int
    action: str
    actor_user_id: int | None = None
    tenant_id: int | None = None
    meta: dict[str, Any] | None = None


def record_audit_event(action: str, actor_user_id: int | None = None, tenant_id: int | None = None, **meta: Any) -> AuditEvent:
    ev = AuditEvent(int(time.time()), action, actor_user_id, tenant_id, meta or None)
    if len(_AUDIT_BUFFER) >= _MAX_BUFFER:
        del _AUDIT_BUFFER[0: max(50, _MAX_BUFFER // 10)]  # drop oldest slice
    _AUDIT_BUFFER.append(asdict(ev))
    if trace is not None:  # pragma: no cover - OTEL optional
        try:
            tracer = trace.get_tracer("yuplan.audit")
            span = tracer.start_span(f"audit.{action}")
            try:
                if actor_user_id is not None:
                    span.set_attribute("actor_user_id", actor_user_id)
                if tenant_id is not None:
                    span.set_attribute("tenant_id", tenant_id)
                for k, v in meta.items():
                    span.set_attribute(f"meta.{k}", str(v))
            finally:
                span.end()
        except Exception:
            pass
    return ev


def list_audit_events() -> list[dict[str, Any]]:  # pragma: no cover - convenience
    return list(_AUDIT_BUFFER)
