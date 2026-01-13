"""Department Portal API (Skeleton Phase 1)

Provides read-only composite week payload at:
  GET /portal/department/week?year=YYYY&week=WW

Authentication: expected header (temporary) `X-Department-Id` carrying department_id.
In later phases this will be resolved from token/role claims instead.

This skeleton focuses on shape compliance with `docs/department_portal_week_schema.md`.
Business logic (menu texts, residents, diets) is deferred.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha1
import json
from flask import Blueprint, request, jsonify, Response

from portal.department.models import DepartmentPortalWeekPayload
from portal.department.service import build_department_week_payload
from portal.department.auth import get_department_id_from_claims
from portal.department.menu_choice_repo import MenuChoiceRepo
from core.http_errors import forbidden
from core.errors import bad_request

bp = Blueprint("portal_department", __name__, url_prefix="/portal/department")


_WEEKDAY_NAMES_SV = [
    "Måndag",
    "Tisdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lördag",
    "Söndag",
]


def _iso_week_start(year: int, week: int) -> datetime:
    """Return a datetime for the Monday of the given ISO year/week."""
    # Using ISO calendar: construct Monday by parsing year-week-1 pattern
    return datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")


@bp.get("/week")
def get_department_week():  # type: ignore[override]
    year_raw = request.args.get("year")
    week_raw = request.args.get("week")
    # Department scoping from JWT/claims (helper aborts 403 if missing)
    try:
        dept_id = get_department_id_from_claims()
    except Exception:
        return forbidden(detail="department_claim_missing")
    try:
        year = int(year_raw or "")
        week = int(week_raw or "")
    except ValueError:
        return bad_request("invalid_year_or_week")
    if year < 2000 or year > 2100 or week < 1 or week > 53:
        return bad_request("invalid_range")
    try:
        _iso_week_start(year, week)
    except ValueError:
        return bad_request("invalid_week_reference")

    payload: DepartmentPortalWeekPayload = build_department_week_payload(dept_id, year, week)
    # Aggregate portal-level ETag from component map
    etag_sig = sha1(json.dumps(payload["etag_map"], sort_keys=True).encode()).hexdigest()[:12]
    portal_etag = f'W/"portal-dept-week:{dept_id}:{year}-{week}:{etag_sig}"'
    inm = request.headers.get("If-None-Match")
    if inm and portal_etag in [p.strip() for p in inm.split(",") if p.strip()]:
        resp = Response(status=304)
        resp.headers["ETag"] = portal_etag
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    resp = jsonify(payload)
    resp.headers["ETag"] = portal_etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp


@bp.post("/menu-choice/change")
def change_menu_choice():  # type: ignore[override]
    """Change menu choice (Alt1/Alt2) for a given weekday.

    Concurrency: requires If-Match header matching current menu_choice ETag.
    Body JSON: {year, week, weekday, selected_alt}
    Weekday accepted forms: Mon,Tue,Wed,Thu,Fri,Sat,Sun (case-insensitive).
    Returns: {new_etag, selected_alt} with 200 or appropriate error.
    """
    dept_id = get_department_id_from_claims()
    data = request.get_json(silent=True) or {}
    year = data.get("year")
    week = data.get("week")
    weekday_raw = data.get("weekday")
    selected_alt = data.get("selected_alt")
    if_match = request.headers.get("If-Match")
    if not if_match:
        return bad_request("missing_if_match")
    # Basic validation
    try:
        year = int(year)
        week = int(week)
    except (TypeError, ValueError):
        return bad_request("invalid_year_or_week")
    if year < 2000 or year > 2100 or week < 1 or week > 53:
        return bad_request("invalid_range")
    if not isinstance(weekday_raw, str):
        return bad_request("weekday_required")
    weekday_norm = weekday_raw.strip().lower()[:3]
    _WK_MAP = {"mon":1,"tue":2,"wed":3,"thu":4,"fri":5,"sat":6,"sun":7}
    if weekday_norm not in _WK_MAP:
        return bad_request("invalid_weekday")
    if selected_alt not in {"Alt1","Alt2"}:
        return bad_request("invalid_selected_alt")
    # Current signature
    repo = MenuChoiceRepo()
    current_sig = repo.get_signature(dept_id, year, week)
    if if_match != current_sig:
        # Concurrency failure – current signature differs from provided If-Match
        from core.http_errors import problem as _problem
        return _problem(412, "etag_mismatch", "Precondition Failed", "etag_mismatch")
    # Persist choice
    repo.set_choice(dept_id, week, _WK_MAP[weekday_norm], selected_alt)
    new_sig = repo.get_signature(dept_id, year, week)
    return jsonify({"new_etag": new_sig, "selected_alt": selected_alt})
