from __future__ import annotations

import uuid
from typing import Any, Optional

from flask import Blueprint, Response, current_app, jsonify, request, session, g

from .auth import require_roles
from .http_errors import bad_request, not_found, forbidden, problem
from .weekview.service import WeekviewService, EtagMismatchError

bp = Blueprint("weekview_api", __name__, url_prefix="/api")
_service = WeekviewService()


def _feature_enabled(name: str) -> bool:
    # Tenant override first
    override = getattr(g, "tenant_feature_flags", {}).get(name)
    if override is not None:
        return bool(override)
    try:
        reg = getattr(current_app, "feature_registry", None)
        if reg is not None:
            return bool(reg.enabled(name))
    except Exception:
        pass
    return False


def _require_weekview_enabled() -> Response | None:
    if not _feature_enabled("ff.weekview.enabled"):
        return not_found("weekview_disabled")
    return None


def _tenant_id() -> Any:
    tid = session.get("tenant_id")
    if not tid:
        # In tests, this should be set via header injector; treat missing as 401
        return None
    return tid


@bp.get("/weekview")
@require_roles("admin", "editor", "viewer")
def get_weekview() -> Response:
    maybe = _require_weekview_enabled()
    if maybe is not None:
        return maybe
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return bad_request("invalid_year_or_week")
    if year < 1970 or not (1 <= week <= 53):
        return bad_request("invalid_year_or_week")
    department_id = request.args.get("department_id") or None
    # Validate UUID if present (best-effort)
    if department_id:
        try:
            uuid.UUID(department_id)
        except Exception:
            return bad_request("invalid_department_id")
    payload, etag = _service.fetch_weekview(tid, year, week, department_id)
    resp = jsonify(payload)
    resp.headers["ETag"] = etag
    return resp


@bp.get("/weekview/resolve")
@require_roles("admin", "editor", "viewer")
def resolve_weekview() -> Response:
    maybe = _require_weekview_enabled()
    if maybe is not None:
        return maybe
    # Minimal idempotent helper
    site = (request.args.get("site") or "").strip()
    dep = (request.args.get("department_id") or "").strip()
    date = (request.args.get("date") or "").strip()
    if not site or not dep or not date:
        return bad_request("invalid_parameters")
    try:
        uuid.UUID(dep)
    except Exception:
        return bad_request("invalid_department_id")
    data = _service.resolve(site, dep, date)
    return jsonify({"ok": True, **data})


@bp.patch("/weekview")
@require_roles("admin", "editor")
def patch_weekview() -> Response:
    maybe = _require_weekview_enabled()
    if maybe is not None:
        return maybe
    # Require If-Match header
    etag = request.headers.get("If-Match")
    if not etag:
        return bad_request("missing_if_match")
    data = request.get_json(silent=True) or {}
    # Allow tenant from context; if provided in body ensure match
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    body_tid = data.get("tenant_id")
    if body_tid is not None and str(body_tid) != str(tid):
        return bad_request("tenant_mismatch")
    department_id = (data.get("department_id") or "").strip()
    try:
        year = int(data.get("year", 0))
        week = int(data.get("week", 0))
    except Exception:
        return bad_request("invalid_year_or_week")
    if not department_id:
        return bad_request("invalid_department_id")
    try:
        uuid.UUID(department_id)
    except Exception:
        return bad_request("invalid_department_id")
    if year < 1970 or not (1 <= week <= 53):
        return bad_request("invalid_year_or_week")
    ops = data.get("operations") or []
    if not isinstance(ops, list):
        return bad_request("invalid_operations")
    allowed_meals = {"lunch", "dinner"}
    for op in ops:
        try:
            dow = int(op.get("day_of_week"))
            meal = str(op.get("meal"))
            diet = str(op.get("diet_type"))
        except Exception:
            return bad_request("invalid_operations")
        if dow < 1 or dow > 7:
            return bad_request("invalid_day_of_week")
        if meal not in allowed_meals:
            return bad_request("invalid_meal")
        if not diet:
            return bad_request("invalid_diet_type")
    try:
        new_etag = _service.toggle_marks(tid, year, week, department_id, etag, ops)
    except EtagMismatchError:
        return problem(412, "https://example.com/errors/etag_mismatch", "Precondition Failed", "etag_mismatch")
    resp = jsonify({"updated": len(ops)})
    resp.headers["ETag"] = new_etag
    return resp
