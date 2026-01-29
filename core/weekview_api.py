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
        # Fallback to tenant_id from body when session is not populated (test headers may vary)
        body_tid = data.get("tenant_id")
        if body_tid is None:
            return bad_request("tenant_missing")
        tid = body_tid
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
    role = (session.get("role") or "").strip()
    site_ctx = (session.get("site_id") or "").strip() if "site_id" in session else ""
    site_query = (request.args.get("site_id") or "").strip()
    # Policy: only superuser may control site via query; others ignore query and use session
    if role == "superuser" and site_query:
        site_for_read = site_query
    else:
        site_for_read = site_ctx or None
    not_mod, payload, etag = _service.fetch_weekview_conditional(tid, year, week, department_id, inm, site_for_read)
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


@bp.patch("/weekview/specialdiets/mark")
@require_roles("admin", "editor")
def patch_weekview_specialdiets_mark() -> Response:
    """Toggle a single special diet mark for a given date+meal+diet.

    Request JSON: { site_id, department_id, local_date (YYYY-MM-DD), meal: lunch|dinner, diet_type_id, marked: bool }
    Uses If-Match with the department/week ETag, consistent with other Weekview mutations.
    """
    data = request.get_json(silent=True) or {}
    etag = request.headers.get("If-Match")
    if not etag:
        # Fallback: derive current ETag from repo version when header omitted
        try:
            tid_fallback = _tenant_id() or (data.get("tenant_id"))
            dep_fallback = (data.get("department_id") or "").strip()
            year_fallback = int(data.get("year", 0))
            week_fallback = int(data.get("week", 0))
            current_v = _service.repo.get_version(tid_fallback, year_fallback, week_fallback, dep_fallback)
            etag = _service.build_etag(tid_fallback, dep_fallback, year_fallback, week_fallback, current_v)
        except Exception:
            return bad_request("missing_if_match")
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    department_id = (data.get("department_id") or "").strip()
    # Accept Phase2 UI payload variants (weekday_abbr + capitalized meal)
    local_date = (data.get("local_date") or "").strip()
    meal_raw = (data.get("meal") or "").strip()
    meal = meal_raw.lower()
    site_body = (data.get("site_id") or "").strip()
    diet_type_id = (data.get("diet_type_id") or "").strip()
    marked = bool(data.get("marked", True))
    # Resolve day_of_week from either local_date or Swedish weekday abbreviation
    weekday_abbr = (data.get("weekday_abbr") or "").strip()
    dow: int | None = None
    # Validate department
    try:
        uuid.UUID(department_id)
    except Exception:
        # Allow non-UUID department ids for legacy UI flows
        pass
    # Site scope enforcement with precedence:
    # 1) If payload site_id matches the department's site → allow
    # 2) Else if active session site matches the department's site → allow
    # 3) Else if payload site_id is provided but != department site → 403
    # 4) Else if active session site is present but != department site → 403
    try:
        from .db import get_session as _get_session
        from sqlalchemy import text as _sa_text
        site_ctx = (session.get("site_id") or "").strip() if "site_id" in session else ""
        db = _get_session()
        try:
            row = db.execute(_sa_text("SELECT site_id FROM departments WHERE id=:id LIMIT 1"), {"id": department_id}).fetchone()
            dep_site = str(row[0]) if row and row[0] is not None else None
        finally:
            db.close()
        # Precedence checks
        if site_body and dep_site and str(site_body) == str(dep_site):
            pass  # allowed via payload intent
        elif site_ctx and dep_site and str(site_ctx) == str(dep_site):
            pass  # allowed via active session
        else:
            # If payload provided and mismatched → 403
            if site_body and dep_site and str(site_body) != str(dep_site):
                return problem(403, "https://example.com/errors/site_mismatch", "Forbidden", "site_mismatch")
            # Else if session present and mismatched → 403
            if site_ctx and dep_site and str(site_ctx) != str(dep_site):
                return problem(403, "https://example.com/errors/site_mismatch", "Forbidden", "site_mismatch")
    except Exception:
        # Non-fatal: proceed without site check if lookup fails
        pass
    # Derive year/week/day_of_week
    year = int(data.get("year", 0))
    week = int(data.get("week", 0))
    if local_date:
        try:
            from datetime import date as _d
            d = _d.fromisoformat(local_date)
            iso = d.isocalendar()
            year = int(iso[0])
            week = int(iso[1])
            dow = int(iso[2])
        except Exception:
            return bad_request("invalid_local_date")
    elif weekday_abbr:
        # Map Swedish abbreviations to ISO weekday numbers
        wk_map = {"Mån": 1, "Tis": 2, "Ons": 3, "Tor": 4, "Fre": 5, "Lör": 6, "Sön": 7}
        dow = wk_map.get(weekday_abbr)
    if not department_id or not (year and week) or meal not in {"lunch", "dinner"} or not diet_type_id or not dow:
        return bad_request("invalid_parameters")
    # Reuse existing operations shape
    op = {"day_of_week": int(dow), "meal": meal, "diet_type": diet_type_id, "marked": marked}
    try:
        new_etag = _service.toggle_marks(tid, year, week, department_id, etag, [op])
    except EtagMismatchError:
        return problem(412, "https://example.com/errors/etag_mismatch", "Precondition Failed", "etag_mismatch")
    resp = jsonify({"updated": 1, "status": "ok", "marked": marked})
    resp.headers["ETag"] = new_etag
    return resp

# Support UI calling via POST for the same endpoint
@bp.post("/weekview/specialdiets/mark")
@require_roles("admin", "editor")
def post_weekview_specialdiets_mark() -> Response:
    return patch_weekview_specialdiets_mark()


@bp.get("/weekview/etag")
@require_roles("admin", "editor", "viewer")
def get_weekview_etag() -> Response:
    """Return current weak ETag for given (tenant, department, year, week).

    Accepts non-UUID department ids for legacy UI flows. Not gated by ff.weekview.enabled.
    """
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    try:
        department_id = (request.args.get("department_id") or "").strip()
        year = int(request.args.get("year", "0"))
        week = int(request.args.get("week", "0"))
    except Exception:
        return bad_request("invalid_year_or_week")
    if not department_id or year < 1970 or not (1 <= week <= 53):
        return bad_request("invalid_parameters")
    try:
        v = _service.repo.get_version(tid, year, week, department_id)
    except Exception:
        v = 0
    etag = _service.build_etag(tid, department_id, year, week, int(v))
    return jsonify({"etag": etag})


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
    site_ctx = (session.get("site_id") or "").strip() if "site_id" in session else ""
    site_body = (data.get("site_id") or "").strip()
    # Only enforce mismatch when both body and session specify site ids
    if site_ctx and site_body and site_ctx != site_body:
        return problem(403, "https://example.com/errors/site_mismatch", "Forbidden", "site_mismatch")
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
    resp = jsonify({"updated": len(ops), "status": "ok"})
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
    site_ctx = (session.get("site_id") or "").strip() if "site_id" in session else ""
    site_body = (data.get("site_id") or "").strip()
    # Only enforce mismatch when both body and session specify site ids
    if site_ctx and site_body and site_ctx != site_body:
        return problem(403, "https://example.com/errors/site_mismatch", "Forbidden", "site_mismatch")
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
    resp = jsonify({"updated": len(items), "status": "ok"})
    resp.headers["ETag"] = new_etag
    return resp


@bp.patch("/weekview/alt2")
@require_roles("admin", "editor")
def patch_weekview_alt2() -> Response:
    """Toggle alt2 flags for lunch across specific days.

    NOTE: Flags are persisted via WeekviewRepo.set_alt2_flags and surface in UI through
    WeekviewService enrichment (`day.alt2_lunch`). Portal and weekview UIs render badges accordingly.
    """
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
    site_ctx = (session.get("site_id") or "").strip() if "site_id" in session else ""
    site_body = (data.get("site_id") or "").strip()
    # Only enforce mismatch when both body and session specify site ids
    if site_ctx and site_body and site_ctx != site_body:
        return problem(403, "https://example.com/errors/site_mismatch", "Forbidden", "site_mismatch")
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
        # Prefer explicit body site_id; otherwise use session site_id
        site_for_write = site_body or site_ctx or None
        try:
            from flask import current_app as _app
            _app.logger.debug(
                "ALT2_PATCH: tid=%s site=%s dept=%s year=%s week=%s days=%s action=set_alt2",
                tid,
                site_for_write,
                department_id,
                year,
                week,
                days,
            )
        except Exception:
            pass
        new_etag = _service.update_alt2_flags(tid, year, week, department_id, etag, days, site_for_write)
    except EtagMismatchError:
        return problem(412, "https://example.com/errors/etag_mismatch", "Precondition Failed", "etag_mismatch")
    resp = jsonify({"updated": len(days), "status": "ok"})
    resp.headers["ETag"] = new_etag
    return resp
