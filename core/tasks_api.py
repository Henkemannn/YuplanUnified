"""Tasks API

Add precise return annotations using core.api_types; keep runtime JSON stable; no Any.
Delegates core logic to tasks_service for clearer RBAC-typed signatures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from flask import Blueprint, current_app, g, jsonify, request, session, url_for
from flask.typing import ResponseReturnValue

from .api_types import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskId,
    TaskUpdateResponse,
)
from .app_authz import AuthzError, require_roles
from .app_sessions import require_session
from .audit import log_task_status_transition
from .db import get_session
from .deprecation import apply_deprecation
from .deprecation_warn import should_warn, warn_phase_enabled
from .errors import APIError, NotFoundError
from .metrics import increment
from .models import Task
from .pagination import make_page_response, parse_page_params
from .rate_limit import RateLimitExceeded, allow, rate_limited_response
from .roles import to_canonical
from .tasks_service import (
    create_task as svc_create_task,
    list_tasks as svc_list_tasks,
    update_task as svc_update_task,
)

bp = Blueprint("tasks_api", __name__, url_prefix="/tasks")

READ_ROLES = (
    "viewer",
    "editor",
    "admin",
    "superuser",
)  # legacy cook -> viewer, unit_portal -> editor via adapter; superuser allowed
WRITE_ROLES = ("editor", "admin", "superuser")

ALLOWED_STATUS = {"todo", "doing", "blocked", "done", "cancelled"}


def _tenant_id():
    tid = session.get("tenant_id")
    if not tid:
        raise ValueError("tenant missing")
    return tid


def _serialize(t: Task):
    return {
        "id": t.id,
        "title": t.title,
        "task_type": t.task_type,
        "done": t.done,
        "status": getattr(t, "status", "done" if t.done else "todo"),
        "menu_id": t.menu_id,
        "dish_id": t.dish_id,
        "private_flag": t.private_flag,
        "assignee_id": t.assignee_id,
        "creator_user_id": t.creator_user_id,
        "unit_id": t.unit_id,
        "created_at": t.created_at.isoformat() if getattr(t, "created_at", None) else None,
        "updated_at": t.updated_at.isoformat() if getattr(t, "updated_at", None) else None,
    }


@bp.get("/")
@require_roles(*READ_ROLES)
def list_tasks() -> ResponseReturnValue:
    tid = _tenant_id()
    page_req = parse_page_params(dict(request.args))
    db = get_session()
    try:
        role = session.get("role")
        user_id = session.get("user_id")
        # Reuse existing service list (returns full list currently)
        svc_resp = svc_list_tasks(db, tenant_id=tid, user_id=user_id, role=str(role))  # type: ignore[arg-type]
        raw_tasks = svc_resp.get("tasks", [])  # type: ignore[index]
        # Normalize to list[dict[str, object]] for stable sorting while retaining original order source
        tasks: list[dict[str, Any]] = [cast(dict[str, Any], t) for t in list(raw_tasks)]

        # Stable order: created_at (string desc) then id desc. Missing values coerced.
        def _sort_key(t: dict[str, Any]) -> tuple[str, int]:
            created_raw = t.get("created_at")
            created = created_raw if isinstance(created_raw, str) else ""
            ident = t.get("id")
            ident_int = (
                int(ident)
                if isinstance(ident, int) or (isinstance(ident, str) and ident.isdigit())
                else 0
            )
            return (created, ident_int)

        tasks_sorted = sorted(tasks, key=_sort_key, reverse=True)
        total = len(tasks_sorted)
        start = (page_req["page"] - 1) * page_req["size"]
        slice_items = tasks_sorted[start : start + page_req["size"]]
        resp_body = make_page_response(slice_items, page_req, total)
        # Backwards compatibility: legacy tests expect 'tasks' list instead of 'items'
        if "items" in resp_body and "tasks" not in resp_body:
            # Legacy backward compatibility alias; not part of PageResponse schema.
            resp_body["tasks"] = resp_body["items"]  # type: ignore[typeddict-item]
        response = jsonify(resp_body)
        if "tasks" in resp_body:
            apply_deprecation(response, aliases=["tasks"], endpoint="tasks")
        return response
    finally:
        db.close()


@bp.post("/")
@require_roles(*READ_ROLES)
def create_task() -> ResponseReturnValue:
    tid = _tenant_id()
    data = request.get_json(silent=True) or {}
    # Legacy cook (raw role 'cook') should be allowed though it maps to canonical viewer.
    # Canonical viewer (non-cook) remains forbidden for creation.
    sess = require_session(session)
    canonical = to_canonical(sess["role"])  # type: ignore[arg-type]
    if canonical == "viewer":
        # Feature flag gate for legacy cook allowance
        allow_cook = False
        if sess["role"] == "cook":
            # feature flag resolution: per-tenant via g.tenant_feature_flags (populated in app_factory)
            tenant_flags = getattr(g, "tenant_feature_flags", {})
            allow_cook = bool(tenant_flags.get("allow_legacy_cook_create", False))
        if sess["role"] == "cook" and allow_cook:
            tags = {
                "tenant_id": str(sess["tenant_id"]),
                "user_id": str(sess["user_id"]),
                "role": str(sess["role"]),
                "canonical": "viewer",
            }
            if warn_phase_enabled():
                tags["deprecated"] = "soon"
            increment("tasks.create.legacy_cook", tags)
            if should_warn(int(sess["tenant_id"])):
                current_app.logger.warning(
                    "deprecated_legacy_cook_create used tenant=%s user=%s",
                    sess["tenant_id"],
                    sess["user_id"],
                )
        else:
            # canonical viewer or cook without flag blocked
            raise AuthzError("forbidden", required="editor")
    # Rate limit
    try:
        allow(
            tid,
            session.get("user_id"),
            "tasks_mutations",
            60,
            testing=current_app.config.get("TESTING", False),
        )
    except RateLimitExceeded:
        return rate_limited_response()
    db = get_session()
    try:
        # Include legacy 'done' so service can map done True -> status done
        raw_payload = {
            k: v for k, v in data.items() if k in {"title", "assignee", "due", "status", "done"}
        }
        create_payload = cast(TaskCreateRequest, raw_payload)
        result = svc_create_task(
            db,
            tenant_id=tid,
            user_id=session.get("user_id"),
            role=str(session.get("role")),
            payload=create_payload,
        )
        task_id_value = result.get("task_id")  # may be TaskId
        t = db.get(Task, int(task_id_value)) if task_id_value is not None else None  # type: ignore[arg-type]
        if t and task_id_value is not None:
            body: TaskCreateResponse = {
                "ok": True,
                "task_id": TaskId(int(task_id_value)),
                "task": _serialize(t),
            }
        else:
            body = cast(TaskCreateResponse, {"ok": True, **result})
        if t:
            try:
                body["location"] = url_for("tasks_api.get_task", task_id=t.id)
            except Exception:
                body["location"] = f"/tasks/{t.id}"
        # Return 201 Created + Location header (legacy tests rely on this)
        resp = jsonify(body)
        resp.status_code = 201
        loc = body.get("location")
        if loc:
            resp.headers["Location"] = loc
        return resp
    finally:
        db.close()


@bp.get("/<int:task_id>")
@require_roles(*READ_ROLES)
def get_task(task_id: int) -> ResponseReturnValue:
    tid = _tenant_id()
    db = get_session()
    try:
        t = db.query(Task).filter(Task.id == task_id, Task.tenant_id == tid).first()
        if not t:
            raise NotFoundError("task not found")
        role = session.get("role")
        user_id = session.get("user_id")
        if t.private_flag and t.creator_user_id != user_id and role not in ("admin", "superuser"):
            raise AuthzError("forbidden", required="admin")
        return jsonify({"ok": True, "task": _serialize(t)})
    finally:
        db.close()


@bp.put("/<int:task_id>")
@bp.patch("/<int:task_id>")
@require_roles(*WRITE_ROLES)
def update_task(task_id: int) -> ResponseReturnValue:
    tid = _tenant_id()
    db = get_session()
    try:
        # Fetch by id first to differentiate wrong-tenant vs missing
        t = db.query(Task).filter(Task.id == task_id).first()
        if not t:
            raise NotFoundError("task not found")
        if t.tenant_id != tid:
            raise AuthzError("forbidden", required="admin")
        role = session.get("role")
        user_id = session.get("user_id")
        # Ownership enforcement:
        # Tests assert non-owner (cook) cannot update another user's task even if public.
        # Allow only creator OR admin/superuser.
        if role not in ("admin", "superuser") and t.creator_user_id != user_id:
            raise AuthzError("forbidden", required="editor")
        try:
            allow(
                tid,
                user_id,
                "tasks_mutations",
                60,
                testing=current_app.config.get("TESTING", False),
            )
        except RateLimitExceeded:
            return rate_limited_response()
        raw = request.get_json(silent=True) or {}
        # Whitelist allowed update keys to keep typing predictable
        data_keys = {
            k: v
            for k, v in raw.items()
            if k
            in {
                "title",
                "status",
                "done",
                "private_flag",
                "assignee_id",
                "menu_id",
                "dish_id",
            }
        }
        data = data_keys  # local alias
        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                # Legacy tests expect 400 bad_request for invalid input here
                raise APIError("title required", error="bad_request", status=400)
            t.title = title
        if "status" in data:
            status = data.get("status")
            if status not in ALLOWED_STATUS:
                allowed_list = ", ".join(sorted(ALLOWED_STATUS))
                # Raise 400 with detailed message containing allowed list (tests assert tokens present)
                raise APIError(
                    f"Invalid status '{status}'. Allowed: {allowed_list}.",
                    error="bad_request",
                    status=400,
                )
            old_status = getattr(t, "status", "done" if t.done else "todo")
            t.done = status == "done"
            if hasattr(t, "status"):
                t.status = status
            log_task_status_transition(db, t, old_status, status, user_id)
        if "done" in data:
            t.done = bool(data.get("done"))
            if (
                hasattr(t, "status") and "status" not in data
            ):  # keep status in sync when legacy done used
                new_status = "done" if t.done else "todo"
                old_status = getattr(t, "status", new_status)
                if hasattr(t, "status"):
                    log_task_status_transition(db, t, old_status, new_status, user_id)
                    t.status = new_status
        if "private_flag" in data:
            t.private_flag = bool(data.get("private_flag"))
        if "assignee_id" in data:
            t.assignee_id = data.get("assignee_id")
        if "menu_id" in data:
            t.menu_id = data.get("menu_id")
        if "dish_id" in data:
            t.dish_id = data.get("dish_id")
        # touch updated_at if column exists
        if hasattr(t, "updated_at"):
            from contextlib import suppress

            with suppress(Exception):
                t.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(t)
        # Also invoke service update for future parity (idempotent)
        try:
            svc_update_task(
                db,
                tenant_id=tid,
                user_id=user_id,
                role=str(role),
                task_id=task_id,
                payload=data,  # type: ignore[arg-type]
            )
        except Exception:
            # Best-effort; service update is supplementary for now
            pass
        return {"ok": True, "task": _serialize(t)}
    finally:
        db.close()


@bp.delete("/<int:task_id>")
@require_roles(*WRITE_ROLES)
def delete_task(task_id: int) -> ResponseReturnValue:
    tid = _tenant_id()
    db = get_session()
    try:
        t = db.query(Task).filter(Task.id == task_id, Task.tenant_id == tid).first()
        if not t:
            raise NotFoundError("task not found")
        role = session.get("role")
        user_id = session.get("user_id")
        if role not in ("admin", "superuser") and t.creator_user_id != user_id:
            raise AuthzError("forbidden", required="editor")
        try:
            allow(
                tid,
                user_id,
                "tasks_mutations",
                60,
                testing=current_app.config.get("TESTING", False),
            )
        except RateLimitExceeded:
            return rate_limited_response()
        db.delete(t)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
