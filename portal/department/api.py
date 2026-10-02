"""Department portal API."""

from __future__ import annotations

from datetime import date
from hashlib import sha1
import json

from flask import Blueprint, Response, jsonify, request

from core.department_menu_choice_repo import MenuChoiceRepo
from core.http_errors import bad_request, conflict, forbidden, not_found, problem
from portal.department.auth import resolve_department_portal_scope
from portal.department.service import build_department_week_payload
from portal.department.submission_service import DepartmentPortalWeekSubmissionService

bp = Blueprint("portal_department", __name__, url_prefix="/portal/department")


def _iso_week_start(year: int, week: int) -> date:
    return date.fromisocalendar(year, week, 1)


def _resolve_year_week_from_request() -> tuple[int, int] | Response:
    payload = request.get_json(silent=True) or {}
    year_raw = request.args.get("year") or payload.get("year")
    week_raw = request.args.get("week") or payload.get("week")
    try:
        year = int(year_raw or "")
        week = int(week_raw or "")
    except (TypeError, ValueError):
        return bad_request("invalid_year_or_week")
    if year < 2000 or year > 2100 or week < 1 or week > 53:
        return bad_request("invalid_range")
    try:
        _iso_week_start(year, week)
    except ValueError:
        return bad_request("invalid_week_reference")
    return year, week


def _resolve_scope():
    explicit_department_id = (request.args.get("department_id") or "").strip() or None
    try:
        return resolve_department_portal_scope(explicit_department_id=explicit_department_id)
    except Exception:
        return None


@bp.get("/week")
def get_department_week():  # type: ignore[override]
    scope = _resolve_scope()
    if scope is None:
        return forbidden(detail="department_scope_missing")
    resolved = _resolve_year_week_from_request()
    if isinstance(resolved, Response):
        return resolved
    year, week = resolved
    payload = build_department_week_payload(scope, year, week)
    etag_sig = sha1(json.dumps(payload["etag_map"], sort_keys=True).encode("utf-8")).hexdigest()[:12]
    portal_etag = f'W/"portal-dept-week:{scope.department_id}:{year}-{week}:{etag_sig}"'
    inm = request.headers.get("If-None-Match")
    if inm and portal_etag in [value.strip() for value in inm.split(",") if value.strip()]:
        resp = Response(status=304)
        resp.headers["ETag"] = portal_etag
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    resp = jsonify(payload)
    resp.headers["ETag"] = portal_etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp


@bp.get("/week/status")
def get_department_week_status():  # type: ignore[override]
    scope = _resolve_scope()
    if scope is None:
        return forbidden(detail="department_scope_missing")
    resolved = _resolve_year_week_from_request()
    if isinstance(resolved, Response):
        return resolved
    year, week = resolved
    try:
        status = DepartmentPortalWeekSubmissionService().get_status(scope, year, week)
    except ValueError as exc:
        message = str(exc) or "bad_request"
        if message == "publication_missing":
            return not_found(message)
        return bad_request(message)
    return jsonify(status)


@bp.post("/week/submit")
def submit_department_week():  # type: ignore[override]
    scope = _resolve_scope()
    if scope is None:
        return forbidden(detail="department_scope_missing")
    resolved = _resolve_year_week_from_request()
    if isinstance(resolved, Response):
        return resolved
    year, week = resolved
    try:
        status = DepartmentPortalWeekSubmissionService().submit(scope, year, week)
    except ValueError as exc:
        message = str(exc) or "bad_request"
        if message == "publication_missing":
            return not_found(message)
        if message in {"portal_week_not_submittable", "portal_week_incomplete"}:
            return conflict(message)
        return bad_request(message)
    return jsonify(status)


@bp.post("/menu-choice/change")
def change_menu_choice():  # type: ignore[override]
    scope = _resolve_scope()
    if scope is None:
        return forbidden(detail="department_scope_missing")

    data = request.get_json(silent=True) or {}
    year_raw = data.get("year")
    week_raw = data.get("week")
    weekday_raw = data.get("weekday")
    selected_alt_raw = data.get("selected_alt")
    if_match = request.headers.get("If-Match")
    if not if_match:
        return bad_request("missing_if_match")

    try:
        year = int(year_raw)
        week = int(week_raw)
    except (TypeError, ValueError):
        return bad_request("invalid_year_or_week")
    if year < 2000 or year > 2100 or week < 1 or week > 53:
        return bad_request("invalid_range")
    if not isinstance(weekday_raw, str) or not weekday_raw.strip():
        return bad_request("weekday_required")

    weekday_norm = weekday_raw.strip().lower()[:3]
    weekday_map = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7}
    weekday = weekday_map.get(weekday_norm)
    if weekday is None:
        return bad_request("invalid_weekday")

    repo = MenuChoiceRepo()
    current_sig = repo.get_signature(
        tenant_id=scope.tenant_id,
        site_id=scope.site_id,
        department_id=scope.department_id,
        year=year,
        week=week,
    )
    if if_match != current_sig:
        return problem(412, "etag_mismatch", "Precondition Failed", "etag_mismatch")

    selected_alt_text = "" if selected_alt_raw is None else str(selected_alt_raw).strip()
    normalized_alt = selected_alt_text.lower()
    if normalized_alt in {"", "clear", "none", "null", "remove"}:
        repo.clear_choice(
            tenant_id=scope.tenant_id,
            site_id=scope.site_id,
            department_id=scope.department_id,
            year=year,
            week=week,
            weekday=weekday,
        )
        new_selected_alt = None
    elif normalized_alt in {"alt1", "1"}:
        repo.set_choice(
            tenant_id=scope.tenant_id,
            site_id=scope.site_id,
            department_id=scope.department_id,
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="Alt1",
        )
        new_selected_alt = "Alt1"
    elif normalized_alt in {"alt2", "2"}:
        repo.set_choice(
            tenant_id=scope.tenant_id,
            site_id=scope.site_id,
            department_id=scope.department_id,
            year=year,
            week=week,
            weekday=weekday,
            selected_alt="Alt2",
        )
        new_selected_alt = "Alt2"
    else:
        return bad_request("invalid_selected_alt")

    new_sig = repo.get_signature(
        tenant_id=scope.tenant_id,
        site_id=scope.site_id,
        department_id=scope.department_id,
        year=year,
        week=week,
    )
    return jsonify({"new_etag": new_sig, "selected_alt": new_selected_alt})
