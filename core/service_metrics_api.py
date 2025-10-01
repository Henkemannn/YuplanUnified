from __future__ import annotations

from datetime import date
from typing import cast

from flask import Blueprint, current_app, jsonify, request, session

from core.auth import require_roles

from .api_types import (
    ErrorResponse,
    IngestResponse,
    MetricsQueryRowsResponse,
    MetricsSummaryDayResponse,
)

bp = Blueprint("metrics", __name__, url_prefix="/metrics")

def _tenant_id():
    return session.get("tenant_id")

@bp.post("/ingest")
@require_roles("superuser","admin")
def ingest_metrics() -> IngestResponse | ErrorResponse:
    tenant_id = _tenant_id()
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400  # type: ignore[return-value]
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows") or []
    svc = current_app.service_metrics_service  # type: ignore[attr-defined]
    res = svc.ingest(tenant_id, rows)
    return cast(IngestResponse, res)

@bp.post("/query")
@require_roles("superuser","admin","unit_portal")
def query_metrics() -> MetricsQueryRowsResponse | ErrorResponse:
    tenant_id = _tenant_id()
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400  # type: ignore[return-value]
    payload = request.get_json(silent=True) or {}
    filters = payload.get("filters") or {}
    if session.get("role") == "unit_portal":
        filters["unit_ids"] = [session.get("unit_id")]
    svc = current_app.service_metrics_service  # type: ignore[attr-defined]
    rows = svc.query(tenant_id, filters)
    return cast(MetricsQueryRowsResponse, {"ok": True, "rows": rows})

@bp.get("/summary/day")
@require_roles("superuser","admin","unit_portal")
def summary_day() -> MetricsSummaryDayResponse | ErrorResponse:
    tenant_id = _tenant_id()
    if not tenant_id:
        return jsonify({"ok": False, "error": "no tenant context"}), 400  # type: ignore[return-value]
    date_from = request.args.get("from")
    date_to_raw = request.args.get("to")
    if not date_from:
        return jsonify({"ok": False, "error": "missing from"}), 400  # type: ignore[return-value]
    date_to = date_to_raw or date_from
    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except Exception:
        return jsonify({"ok": False, "error": "invalid date"}), 400  # type: ignore[return-value]
    svc = current_app.service_metrics_service  # type: ignore[attr-defined]
    rows = svc.summary_day(tenant_id, df, dt)
    if session.get("role") == "unit_portal":
        uid = session.get("unit_id")
        rows = [r for r in rows if r["unit_id"] == uid]
    return cast(MetricsSummaryDayResponse, {"ok": True, "rows": rows})