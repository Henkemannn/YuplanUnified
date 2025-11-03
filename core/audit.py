"""Audit / logging helper utilities.

Currently minimal; can be extended later to include batching, async dispatch,
or structured event sinks. For now we centralize status transition logging so
API layers stay slimmer and logic (like ignoring no-op transitions) is kept
consistent.
"""
from __future__ import annotations

from flask import g, has_request_context, session as _session
from sqlalchemy.orm import Session

from .audit_repo import AuditRepo
from .models import Task, TaskStatusTransition


def log_event(name: str, **fields) -> None:
    """Persist generic audit event.

    Fields accepted are free-form; tenant_id / actor context inferred when present.
    Fails silently (non-critical path).
    """
    try:
        tenant_id = fields.get("tenant_id")
        if tenant_id is None and has_request_context():
            tenant_id = getattr(g, "tenant_id", None) or _session.get("tenant_id")
        actor_user_id = fields.get("actor_user_id") or (_session.get("user_id") if has_request_context() else None)
        actor_role = fields.get("actor_role") or (_session.get("role") if has_request_context() else None)
        request_id = getattr(g, "request_id", None) if has_request_context() else None
        payload = {k: v for k, v in fields.items() if k not in {"tenant_id", "actor_user_id", "actor_role"}}
        AuditRepo().insert(event=name, tenant_id=tenant_id, actor_user_id=actor_user_id, actor_role=str(actor_role) if actor_role else None, payload=payload, request_id=request_id)
    except Exception:  # pragma: no cover
        return None

def log(name: str, actor_id: int | None = None, tenant_id: int | None = None, meta: dict | None = None) -> None:
    """Convenience helper for emitting audit events.

    Parameters:
      - name: event name
      - actor_id: acting user id (optional; inferred from session if absent)
      - tenant_id: tenant context (optional; inferred if absent)
      - meta: additional payload fields (dict)
    """
    meta = meta or {}
    try:
        kwargs = dict(meta)
        if actor_id is not None:
            kwargs["actor_user_id"] = actor_id
        if tenant_id is not None:
            kwargs["tenant_id"] = tenant_id
        log_event(name, **kwargs)
    except Exception:  # pragma: no cover
        return None

__all__ = ["log_task_status_transition", "log_event", "log"]


def log_task_status_transition(db: Session, task: Task, old_status: str | None, new_status: str, user_id: int | None) -> None:
    """Persist a TaskStatusTransition if there is a real status change.

    Parameters:
        db: SQLAlchemy session
        task: Task instance (must be persistent)
        old_status: previous status (may be None)
        new_status: target status (required)
        user_id: id of user performing change (may be None for system actions)
    """
    # Normalize fallbacks
    if old_status is None:
        old_status = getattr(task, "status", "done" if getattr(task, "done", False) else "todo")
    if new_status is None or old_status == new_status:  # defensive or no-op
        return
    db.add(TaskStatusTransition(task_id=task.id, from_status=old_status, to_status=new_status, changed_by_user_id=user_id))
