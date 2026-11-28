from __future__ import annotations

import uuid
from typing import Any, Optional

from flask import Blueprint, Response, current_app, jsonify, request, session, g, make_response
from sqlalchemy.exc import SQLAlchemyError

from .auth import require_roles
from .http_errors import bad_request, forbidden, not_found, problem
from .report.service import ReportService
from .report.repo import ReportRepo
from .report.export import build_csv, build_xlsx
from .weekview.schema import WeekviewSchemaError


bp = Blueprint("report_api", __name__, url_prefix="/api")
_service = ReportService()
_repo = ReportRepo()


def _feature_enabled(name: str) -> bool:
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


def _require_report_enabled() -> Response | None:
    if not _feature_enabled("ff.report.enabled"):
        return not_found("report_disabled")
    return None


def _tenant_id() -> int | None:
    tid = session.get("tenant_id")
    if not tid:
        return None
    try:
        return int(tid)
    except (TypeError, ValueError):
        return None


def _report_site_id() -> str | Response:
    site_id = str(session.get("site_id") or "").strip()
    if not site_id:
        return forbidden("site_context_required")
    return site_id


def _schema_unavailable() -> Response:
    return problem(
        503,
        "https://example.com/errors/report_schema_unavailable",
        "Service Unavailable",
        "report_schema_unavailable",
    )


@bp.get("/report")
@require_roles("admin", "editor")
def get_report() -> Response:
    maybe = _require_report_enabled()
    if maybe is not None:
        return maybe
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    site_id = _report_site_id()
    if isinstance(site_id, Response):
        return site_id
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return bad_request("invalid_year_or_week")
    if year < 1970 or not (1 <= week <= 53):
        return bad_request("invalid_year_or_week")
    department_id: Optional[str] = request.args.get("department_id") or None
    try:
        if not _repo.site_exists(tid, site_id):
            return not_found("site_not_found")
        if department_id:
            try:
                uuid.UUID(department_id)
            except Exception:
                return bad_request("invalid_department_id")
            if not _repo.department_exists(tid, site_id, year, week, department_id):
                return not_found("department_not_found")
        inm = request.headers.get("If-None-Match")
        not_mod, payload, etag = _service.compute(
            tid, site_id, year, week, department_id, inm
        )
    except (WeekviewSchemaError, SQLAlchemyError):
        current_app.logger.exception("Report schema or data is unavailable")
        return _schema_unavailable()
    if not_mod:
        resp = make_response("")
        resp.status_code = 304
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    resp = jsonify(payload)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp


@bp.get("/report/export")
@require_roles("admin", "editor")
def export_report() -> Response:
    maybe = _require_report_enabled()
    if maybe is not None:
        return maybe
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    site_id = _report_site_id()
    if isinstance(site_id, Response):
        return site_id
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return bad_request("invalid_year_or_week")
    if year < 1970 or not (1 <= week <= 53):
        return bad_request("invalid_year_or_week")
    department_id: Optional[str] = request.args.get("department_id") or None
    fmt = (request.args.get("format") or "").strip().lower()
    if fmt not in ("csv", "xlsx"):
        return bad_request("invalid_format")
    try:
        if not _repo.site_exists(tid, site_id):
            return not_found("site_not_found")
        if department_id:
            try:
                uuid.UUID(department_id)
            except Exception:
                return bad_request("invalid_department_id")
            if not _repo.department_exists(tid, site_id, year, week, department_id):
                return not_found("department_not_found")
        _, payload, base_etag = _service.compute(
            tid, site_id, year, week, department_id, None
        )
    except (WeekviewSchemaError, SQLAlchemyError):
        current_app.logger.exception("Report export schema or data is unavailable")
        return _schema_unavailable()
    inm = request.headers.get("If-None-Match")
    # Suffix ETag with format to differentiate export variants
    export_etag = base_etag[:-1] + f":fmt:{fmt}" + base_etag[-1:]
    if inm and inm == export_etag:
        resp = make_response("")
        resp.status_code = 304
        resp.headers["ETag"] = export_etag
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    # Build bytes
    if fmt == "csv":
        data = build_csv(payload)
        mime = "text/csv"
        ext = "csv"
    else:
        data = build_xlsx(payload)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    filename = f"report_y{year}_w{week}.{ext}"
    resp = make_response(data)
    resp.headers["Content-Type"] = mime
    resp.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    resp.headers["ETag"] = export_etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp
