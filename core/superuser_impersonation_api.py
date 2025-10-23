from __future__ import annotations

from flask import Blueprint, request, session

from .app_authz import require_roles
from .http_errors import bad_request, unprocessable_entity
from .impersonation import get_impersonation, start_impersonation, stop_impersonation
from .audit_events import record_audit_event

bp = Blueprint("superuser_impersonation", __name__, url_prefix="/superuser/impersonate")


@bp.post("/start")
@require_roles("superuser")
def impersonate_start():
    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id")
    reason = (data.get("reason") or "").strip()
    if tenant_id is None:
        return bad_request("tenant_id_required")
    try:
        tenant_id = int(tenant_id)
    except ValueError:
        return unprocessable_entity([{"field": "tenant_id", "msg": "invalid_int"}])
    start_impersonation(tenant_id, reason)
    try:
        record_audit_event(
            "impersonation_started",
            actor_user_id=session.get("user_id"),  # type: ignore[arg-type]
            tenant_id=tenant_id,
            reason=reason,
        )
    except Exception:
        pass
    return {"ok": True, "impersonating": tenant_id}


@bp.post("/stop")
@require_roles("superuser")
def impersonate_stop():
    st = get_impersonation()
    stop_impersonation()
    try:
        record_audit_event(
            "impersonation_ended",
            actor_user_id=session.get("user_id"),  # type: ignore[arg-type]
            tenant_id=getattr(st, "tenant_id", None),
        )
    except Exception:
        pass
    return {"ok": True, "stopped": True, "prev": getattr(st, "tenant_id", None)}
