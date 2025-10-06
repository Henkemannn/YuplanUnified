"""Tasks service layer.

Add precise return annotations using core.api_types; keep runtime JSON stable; no Any.
Service signatures require user_id, role, tenant_id for explicit RBAC context.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .api_types import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskId,
    TaskListResponse,
    TaskSummary,
    TaskUpdateRequest,
    TaskUpdateResponse,
)
from .app_authz import AuthzError
from .audit import log_task_status_transition
from .errors import NotFoundError, ValidationError
from .models import Task

_ALLOWED_STATUS: set[str] = {"todo", "doing", "blocked", "done", "cancelled"}


def _serialize_task(t: Task) -> TaskSummary:  # minimal stable projection
    return {
        "id": TaskId(t.id),
        "title": t.title,
        "status": getattr(t, "status", "done" if t.done else "todo"),
        "owner": t.tenant_id,
        # Additional fields (assignee, due) intentionally omitted for now; extend later
    }


def list_tasks(db: Session, *, tenant_id: int, user_id: int | None, role: str) -> TaskListResponse:
    q = db.query(Task).filter(Task.tenant_id == tenant_id)
    if role not in ("admin", "superuser"):
        # Only non-private or own-created tasks visible
        q = q.filter((~Task.private_flag) | (Task.creator_user_id == user_id))  # type: ignore
    tasks = q.order_by(Task.id.desc()).limit(500).all()
    return {"ok": True, "tasks": [_serialize_task(t) for t in tasks]}


def create_task(db: Session, *, tenant_id: int, user_id: int | None, role: str, payload: TaskCreateRequest) -> TaskCreateResponse:
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError("title required")
    raw_status = payload.get("status")
    legacy_done_flag = bool(payload.get("done"))
    if raw_status is not None:
        if raw_status not in _ALLOWED_STATUS:
            raise ValidationError(f"Invalid status '{raw_status}'.")
        status = raw_status
        done_val = raw_status == "done"
    elif legacy_done_flag:
        status = "done"
        done_val = True
    else:
        status = "todo"
        done_val = False
    t = Task(
        tenant_id=tenant_id,
        unit_id=None,
        task_type="prep",
        title=title,
        done=done_val,
        status=status,
        creator_user_id=user_id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"ok": True, "task_id": TaskId(t.id)}


def update_task(db: Session, *, tenant_id: int, user_id: int | None, role: str, task_id: int, payload: TaskUpdateRequest) -> TaskUpdateResponse:
    t = db.query(Task).filter(Task.id == task_id, Task.tenant_id == tenant_id).first()
    if not t:
        raise NotFoundError("task not found")
    if role not in ("admin", "superuser") and t.creator_user_id != user_id:
        raise AuthzError("forbidden", required="editor")
    changed = False
    if "title" in payload:
        new_title = (payload.get("title") or "").strip()
        if not new_title:
            raise ValidationError("title required")
        if new_title != t.title:
            t.title = new_title
            changed = True
    if "status" in payload:
        new_status = payload.get("status")
        if new_status not in _ALLOWED_STATUS:
            raise ValidationError(f"Invalid status '{new_status}'.")
        old_status = getattr(t, "status", "done" if t.done else "todo")
        if new_status != old_status:
            t.done = new_status == "done"
            if hasattr(t, "status"):
                t.status = new_status  # type: ignore
            log_task_status_transition(db, t, old_status, new_status, user_id)
            changed = True
    if changed and hasattr(t, "updated_at"):
        t.updated_at = datetime.now(UTC)
    if changed:
        db.commit()
        db.refresh(t)
    return {"ok": True, "updated": changed}

__all__ = [
    "list_tasks",
    "create_task",
    "update_task",
]
