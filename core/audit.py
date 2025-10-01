"""Audit / logging helper utilities.

Currently minimal; can be extended later to include batching, async dispatch,
or structured event sinks. For now we centralize status transition logging so
API layers stay slimmer and logic (like ignoring no-op transitions) is kept
consistent.
"""
from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session
from .models import Task, TaskStatusTransition


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
