from __future__ import annotations

from flask import Blueprint, request

from .app_authz import require_roles
from .http_errors import bad_request, unprocessable_entity
from .impersonation import get_impersonation, start_impersonation, stop_impersonation

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
        return unprocessable_entity([{"field":"tenant_id","msg":"invalid_int"}])
    start_impersonation(tenant_id, reason)
    return {"ok": True, "impersonating": tenant_id}

@bp.post("/stop")
@require_roles("superuser")
def impersonate_stop():
    st = get_impersonation()
    stop_impersonation()
    return {"ok": True, "stopped": True, "prev": getattr(st, "tenant_id", None)}
