from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from .app_authz import require_roles
from .audit_repo import AuditQueryFilters, AuditRepo
from .pagination import make_page_response, parse_page_params

bp = Blueprint("admin_audit", __name__, url_prefix="/admin")

@bp.get("/audit")
@require_roles("admin")
def list_audit_events():  # type: ignore[return-value]
    args = request.args
    tenant_id = args.get("tenant_id")
    event = args.get("event")
    q = args.get("q")
    ts_from_s = args.get("from")
    ts_to_s = args.get("to")
    ts_from = datetime.fromisoformat(ts_from_s) if ts_from_s else None
    ts_to = datetime.fromisoformat(ts_to_s) if ts_to_s else None
    try:
        tenant_id_int = int(tenant_id) if tenant_id else None
    except Exception:
        return jsonify({"ok": False, "error": "bad_request", "message": "invalid tenant_id"}), 400
    page_req = parse_page_params(dict(args))
    repo = AuditRepo()
    rows, total = repo.query(
        AuditQueryFilters(
            tenant_id=tenant_id_int,
            event=event,
            ts_from=ts_from,
            ts_to=ts_to,
            text=q,
        ),
        page=page_req["page"],
        size=page_req["size"],
    )
    items = [
        {
            "id": r.id,
            "ts": r.ts.isoformat(),
            "tenant_id": r.tenant_id,
            "actor_user_id": r.actor_user_id,
            "actor_role": r.actor_role,
            "event": r.event,
            "payload": r.payload,
            "request_id": r.request_id,
        }
        for r in rows
    ]
    return jsonify(make_page_response(items, page_req, total))
