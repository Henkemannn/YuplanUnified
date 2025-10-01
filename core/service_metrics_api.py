from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, jsonify, request, session

from core.auth import require_roles

bp = Blueprint("metrics", __name__, url_prefix="/metrics")

def _tenant_id():
    return session.get("tenant_id")

@bp.post("/ingest")
@require_roles("superuser","admin")
def ingest_metrics():
    tenant_id = _tenant_id()
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows") or []
    svc = current_app.service_metrics_service  # type: ignore[attr-defined]
    res = svc.ingest(tenant_id, rows)
    return res

@bp.post("/query")
@require_roles("superuser","admin","unit_portal")
def query_metrics():
    tenant_id = _tenant_id()
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    payload = request.get_json(silent=True) or {}
    filters = payload.get("filters") or {}
    # unit_portal restriction
    if session.get("role") == "unit_portal":
        filters["unit_ids"] = [session.get("unit_id")]
    svc = current_app.service_metrics_service  # type: ignore[attr-defined]
    rows = svc.query(tenant_id, filters)
    return {"ok": True, "rows": rows}

@bp.get("/summary/day")
@require_roles("superuser","admin","unit_portal")
def summary_day():
    tenant_id = _tenant_id()
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400
    date_from = request.args.get("from")
    date_to = request.args.get("to") or date_from
    if not date_from:
        return jsonify({"ok": False, "error": "missing from"}), 400
    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except Exception:
        return jsonify({"ok": False, "error": "invalid date"}), 400
    svc = current_app.service_metrics_service  # type: ignore[attr-defined]
    rows = svc.summary_day(tenant_id, df, dt)
    # portal restriction filter
    if session.get("role") == "unit_portal":
        uid = session.get("unit_id")
        rows = [r for r in rows if r["unit_id"] == uid]
    return {"ok": True, "rows": rows}