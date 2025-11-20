from __future__ import annotations

import uuid
from datetime import date as _date
from typing import Any

from flask import Blueprint, jsonify, request, session, make_response

from .auth import require_roles
from .http_errors import bad_request, not_found
from .db import get_session

bp = Blueprint("planera_api", __name__, url_prefix="/api")


def _tenant_id() -> Any:
    tid = session.get("tenant_id")
    if not tid:
        return None
    return tid


def _build_etag(kind: str, parts: list[str]) -> str:
    base = ":".join(parts)
    return f'W/"planera:{kind}:{base}"'


def _conditional(etag: str) -> Any:
    inm = request.headers.get("If-None-Match")
    if inm and inm == etag:
        resp = make_response("")
        resp.status_code = 304
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    return None


def _validate_site_and_department(site_id: str, department_id: str | None) -> tuple[str, list[dict]] | None:
    """Return (site_name, departments) or None if invalid (already produced a response)."""
    db = get_session()
    try:
        row = db.execute(
            __import__("sqlalchemy").text("SELECT id, name FROM sites WHERE id = :i"), {"i": site_id}
        ).fetchone()
        if not row:
            return None
        site_name = str(row[1])
        q = "SELECT id, name FROM departments WHERE site_id = :s"
        params = {"s": site_id}
        if department_id:
            q += " AND id = :d"
            params["d"] = department_id
        rows = db.execute(__import__("sqlalchemy").text(q), params).fetchall()
        if department_id and not rows:
            return None
        deps = [{"department_id": str(r[0]), "department_name": str(r[1])} for r in rows]
        return site_name, deps
    finally:
        db.close()


def _meal_labels(site_id: str) -> dict[str, str]:
    # Reuse existing helper if available; fallback defaults.
    try:
        from .ui_blueprint import get_meal_labels_for_site  # type: ignore
        return get_meal_labels_for_site(site_id)
    except Exception:
        return {"lunch": "Lunch", "dinner": "Kvällsmat"}


def _empty_meal() -> dict[str, Any]:
    return {"residents_total": 0, "special_diets": [], "normal_diet_count": 0}


@bp.get("/planera/day")
@require_roles("admin", "editor", "viewer")
def get_planera_day():
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    site_id = (request.args.get("site_id") or "").strip()
    date_str = (request.args.get("date") or "").strip()
    department_id = (request.args.get("department_id") or "").strip() or None
    if not site_id or not date_str:
        return bad_request("invalid_parameters")
    try:
        uuid.UUID(site_id)
        if department_id:
            uuid.UUID(department_id)
        _d = _date.fromisoformat(date_str)
    except Exception:
        return bad_request("invalid_parameters")
    ok = _validate_site_and_department(site_id, department_id)
    if not ok:
        return not_found("site_or_department_not_found")
    site_name, deps = ok
    meal_labels = _meal_labels(site_id)
    departments_out = []
    for d in deps:
        departments_out.append(
            {
                "department_id": d["department_id"],
                "department_name": d["department_name"],
                "meals": {"lunch": _empty_meal(), "dinner": _empty_meal()},
            }
        )
    totals = {"lunch": _empty_meal(), "dinner": _empty_meal()}
    payload = {
        "site_id": site_id,
        "site_name": site_name,
        "date": date_str,
        "meal_labels": meal_labels,
        "departments": departments_out,
        "totals": totals,
    }
    etag = _build_etag("day", [site_id, date_str])
    maybe = _conditional(etag)
    if maybe is not None:
        return maybe
    resp = jsonify(payload)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp


@bp.get("/planera/week")
@require_roles("admin", "editor", "viewer")
def get_planera_week():
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    site_id = (request.args.get("site_id") or "").strip()
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return bad_request("invalid_parameters")
    department_id = (request.args.get("department_id") or "").strip() or None
    if not site_id or year < 2000 or year > 2100 or week < 1 or week > 53:
        return bad_request("invalid_parameters")
    try:
        uuid.UUID(site_id)
        if department_id:
            uuid.UUID(department_id)
    except Exception:
        return bad_request("invalid_parameters")
    ok = _validate_site_and_department(site_id, department_id)
    if not ok:
        return not_found("site_or_department_not_found")
    site_name, deps = ok
    meal_labels = _meal_labels(site_id)
    departments_ids = [d["department_id"] for d in deps]
    # Build days array (dummy data)
    day_objs: list[dict[str, Any]] = []
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for dow in range(1, 8):
        date_str = None
        try:
            date_str = _date.fromisocalendar(year, week, dow).isoformat()
        except Exception:
            date_str = ""
        day_objs.append(
            {
                "day_of_week": dow,
                "date": date_str,
                "weekday_name": weekday_names[dow - 1],
                "meals": {"lunch": _empty_meal(), "dinner": _empty_meal()},
            }
        )
    weekly_totals = {"lunch": _empty_meal(), "dinner": _empty_meal()}
    payload = {
        "site_id": site_id,
        "site_name": site_name,
        "year": year,
        "week": week,
        "meal_labels": meal_labels,
        "days": day_objs,
        "weekly_totals": weekly_totals,
    }
    etag = _build_etag("week", [site_id, str(year), str(week), ":".join(departments_ids)])
    maybe = _conditional(etag)
    if maybe is not None:
        return maybe
    resp = jsonify(payload)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp
