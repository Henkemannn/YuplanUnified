from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, session, g, make_response

from .auth import require_roles
from .http_errors import bad_request, not_found, problem
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
    inm = request.headers.get("If-None-Match")
    not_mod, payload, etag = _service.fetch_weekview_conditional(tid, year, week, department_id, inm)
    if not_mod:
        resp = make_response("")
        resp.status_code = 304
        resp.headers["ETag"] = etag
        # Enable client caching validation
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    resp = jsonify(payload)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
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


@bp.patch("/weekview/residents")
@require_roles("admin", "editor")
def patch_weekview_residents() -> Response:
    maybe = _require_weekview_enabled()
    if maybe is not None:
        return maybe
    etag = request.headers.get("If-Match")
    if not etag:
        return bad_request("missing_if_match")
    data = request.get_json(silent=True) or {}
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
    items = data.get("items") or []
    if not isinstance(items, list):
        return bad_request("invalid_items")
    allowed_meals = {"lunch", "dinner"}
    for it in items:
        try:
            dow = int(it.get("day_of_week"))
            meal = str(it.get("meal"))
            cnt = int(it.get("count"))
        except Exception:
            return bad_request("invalid_items")
        if dow < 1 or dow > 7:
            return bad_request("invalid_day_of_week")
        if meal not in allowed_meals:
            return bad_request("invalid_meal")
        if cnt < 0:
            return bad_request("invalid_count")
    try:
        new_etag = _service.update_residents_counts(tid, year, week, department_id, etag, items)
    except EtagMismatchError:
        return problem(412, "https://example.com/errors/etag_mismatch", "Precondition Failed", "etag_mismatch")
    resp = jsonify({"updated": len(items)})
    resp.headers["ETag"] = new_etag
    return resp


@bp.patch("/weekview/alt2")
@require_roles("admin", "editor")
def patch_weekview_alt2() -> Response:
    maybe = _require_weekview_enabled()
    if maybe is not None:
        return maybe
    etag = request.headers.get("If-Match")
    if not etag:
        return bad_request("missing_if_match")
    data = request.get_json(silent=True) or {}
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
    days = data.get("days") or []
    if not isinstance(days, list):
        return bad_request("invalid_days")
    for d in days:
        try:
            di = int(d)
        except Exception:
            return bad_request("invalid_days")
        if di < 1 or di > 7:
            return bad_request("invalid_day_of_week")
    try:
        new_etag = _service.update_alt2_flags(tid, year, week, department_id, etag, days)
    except EtagMismatchError:
        return problem(412, "https://example.com/errors/etag_mismatch", "Precondition Failed", "etag_mismatch")
    resp = jsonify({"updated": len(days)})
    resp.headers["ETag"] = new_etag
    return resp
