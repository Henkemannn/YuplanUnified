from __future__ import annotations

import uuid
from typing import Any, Optional

from flask import Blueprint, Response, current_app, jsonify, request, session, g

from .auth import require_roles
from .http_errors import bad_request, not_found, forbidden, problem
from .weekview.service import WeekviewService

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
    # Phase A: Not Implemented
    return problem(
        501,
        "https://example.com/errors/not_implemented",
        "Not Implemented",
        "weekview_patch_phaseA",
    )
