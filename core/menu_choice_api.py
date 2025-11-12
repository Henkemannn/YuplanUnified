from __future__ import annotations

"""Menu choice (Alt1/Alt2) per (department, week, day) – Pass B API.

Implements GET/PUT /admin/menu-choice with ETag concurrency similar to other admin endpoints.

ETag format (per department+week collection): W/"admin:menu-choice:<department_id>:<week>:v<version>"

Days mapping: 1..7 -> mon..sun. Absence of a flag row => Alt1.
Weekend (sat/sun) does not allow Alt2 – returns 422 ProblemDetails.
"""

from flask import Blueprint, request, jsonify

from .auth import require_roles
from .http_errors import bad_request, problem
from .etag import parse_if_match, make_etag
from .admin_repo import Alt2Repo
from .db import get_session

bp = Blueprint("menu_choice", __name__, url_prefix="/admin")

_DAY_MAP = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}
_REV_DAY_MAP = {v: k for k, v in _DAY_MAP.items()}
_WEEKEND = {6, 7}


def _current_version(department_id: str, week: int) -> int:
    db = get_session()
    try:
        row = db.execute(
            # max version across alt2_flags rows for this dept+week
            # table created implicitly by Alt2Repo operations if needed
            # returns 0 if no rows
            # noqa: E501
            "SELECT COALESCE(MAX(version),0) FROM alt2_flags WHERE department_id=:d AND week=:w",
            {"d": department_id, "w": int(week)},
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        db.close()


def _make_coll_etag(department_id: str, week: int, version: int) -> str:
    return make_etag("admin", "menu-choice", f"{department_id}:{week}", version)


@bp.get("/menu-choice")
@require_roles("admin", "editor")
def get_menu_choice():  # type: ignore[return-value]
    try:
        week = int(request.args.get("week", ""))
    except Exception:
        return bad_request("week query param required/int")
    if week < 1 or week > 53:
        return bad_request("Week must be between 1 and 53")
    department_id = request.args.get("department") or request.args.get("department_id")
    if not department_id:
        return bad_request("department query param required")

    repo = Alt2Repo()
    rows = [r for r in repo.list_for_week(week) if r["department_id"] == department_id]
    # Build days mapping; default Alt1
    days: dict[str, str] = {v: "Alt1" for v in _DAY_MAP.values()}
    for r in rows:
        if r["enabled"]:
            day_key = _DAY_MAP.get(int(r["weekday"]))
            if day_key:
                days[day_key] = "Alt2"
    version = _current_version(department_id, week)
    etag = _make_coll_etag(department_id, week, version)
    if_none = request.headers.get("If-None-Match")
    if if_none and etag in [p.strip() for p in if_none.split(",") if p.strip()]:
        from flask import Response
        resp = Response(status=304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    body = {"week": week, "department": department_id, "days": days}
    resp = jsonify(body)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp


@bp.put("/menu-choice")
@require_roles("admin", "editor")
def put_menu_choice():  # type: ignore[return-value]
    data = request.get_json(silent=True) or {}
    try:
        week = int(data.get("week"))
    except Exception:
        return bad_request("week required/int")
    if week < 1 or week > 53:
        return bad_request("Week must be between 1 and 53")
    department_id = str(data.get("department") or data.get("department_id") or "").strip()
    if not department_id:
        return bad_request("department required")
    day = str(data.get("day") or "").strip().lower()
    if day not in _REV_DAY_MAP:
        return bad_request("day invalid")
    choice = str(data.get("choice") or "").strip()
    if choice not in {"Alt1", "Alt2"}:
        return bad_request("choice invalid")
    weekday_num = _REV_DAY_MAP[day]
    if weekday_num in _WEEKEND and choice == "Alt2":
        # 422 ProblemDetails per brief
        return problem(
            422,
            "https://yuplan.dev/problems/menu-choice/alt2-weekend",
            "Alt2 not permitted on weekends",
            "Alt2 is only available Monday–Friday.",
            week=week,
            department=department_id,
            day=day,
        )

    # Concurrency (If-Match)
    if_match = request.headers.get("If-Match")
    ns, kind, ident, version = parse_if_match(if_match)
    if version is None or ns != "admin" or kind != "menu-choice" or ident != f"{department_id}:{week}":
        from .http_errors import problem as _pb
        return _pb(412, "etag_mismatch", "Precondition Failed", "etag_mismatch")
    current_v = _current_version(department_id, week)
    if version != current_v:
        from .http_errors import problem as _pb
        cur_etag = _make_coll_etag(department_id, week, current_v)
        resp = _pb(412, "etag_mismatch", "Precondition Failed", "Resource has been modified")
        try:
            payload = resp.get_json()
            payload["current_etag"] = cur_etag
            from flask import jsonify as _j
            resp = _j(payload)
            resp.status_code = 412
            return resp
        except Exception:
            return resp

    # Upsert single flag row
    # Need site_id for Alt2Repo bulk_upsert
    db = get_session()
    try:
        row = db.execute(
            "SELECT site_id FROM departments WHERE id=:id", {"id": department_id}
        ).fetchone()
        if not row:
            return bad_request("department_not_found")
        site_id = str(row[0])
    finally:
        db.close()
    repo = Alt2Repo()
    enabled = choice == "Alt2"
    # Use bulk_upsert with single item; ensure weekday numbering matches storage (1..7)
    repo.bulk_upsert(
        [
            {
                "site_id": site_id,
                "department_id": department_id,
                "week": week,
                "weekday": weekday_num,
                "enabled": enabled,
            }
        ]
    )
    new_version = _current_version(department_id, week)
    new_etag = _make_coll_etag(department_id, week, new_version)
    from flask import Response
    resp = Response(status=204)
    resp.headers["ETag"] = new_etag
    return resp


__all__ = ["bp"]
