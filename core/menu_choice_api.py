from __future__ import annotations

"""Menu choice (Alt1/Alt2) per (department, week, day) – Pass B API.

Implements GET/PUT /admin/menu-choice with ETag concurrency similar to other admin endpoints.

ETag format (per department+year+week collection): W/"admin:menu-choice:<department_id>:<year>:<week>:v<version>"

Days mapping: 1..7 -> mon..sun. Absence of a canonical row => None / no explicit choice.
Weekend (sat/sun) does not allow Alt2 – returns 422 ProblemDetails.
"""

from datetime import date as _date
from hashlib import sha1
import json

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from core.context import get_active_context

from .auth import require_roles
from .http_errors import bad_request, problem
from .etag import parse_if_match, make_etag
from .db import get_session
from core.db import get_site_tenant
from core.department_menu_choice_repo import MenuChoiceRepo

bp = Blueprint("menu_choice", __name__, url_prefix="/admin")

_DAY_MAP = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}
_REV_DAY_MAP = {v: k for k, v in _DAY_MAP.items()}
_WEEKEND = {6, 7}


def _tenant_id() -> int:
    ctx = get_active_context()
    tenant_id = ctx.get("tenant_id")
    if isinstance(tenant_id, int) and tenant_id > 0:
        return tenant_id
    if isinstance(tenant_id, str) and tenant_id.isdigit():
        return int(tenant_id)
    return 0


def _resolve_department_scope(department_id: str, tenant_id: int, active_site_id: str | None) -> tuple[str, int]:
    db = get_session()
    try:
        row = db.execute(
            text("SELECT site_id FROM departments WHERE id=:id"),
            {"id": department_id},
        ).fetchone()
        if not row:
            raise ValueError("department_not_found")
        site_id = str(row[0] or "").strip()
        if not site_id:
            raise ValueError("department_not_found")
        site_tenant_id = get_site_tenant(site_id)
        if site_tenant_id is None:
            raise ValueError("department_not_found")
        if tenant_id and int(site_tenant_id) != int(tenant_id):
            raise ValueError("department_not_found")
        if active_site_id and str(active_site_id).strip() != site_id:
            raise ValueError("department_not_found")
        return site_id, int(site_tenant_id)
    finally:
        db.close()


def _current_iso_year() -> int:
    return int(_date.today().isocalendar()[0])


def _collection_version_from_rows(rows: list) -> int:
    payload = [
        {
            "weekday": int(row.weekday),
            "meal": str(row.meal),
            "selected_variant": str(row.selected_variant),
            "version": int(row.version),
        }
        for row in rows
    ]
    sig = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return int(sha1(sig.encode()).hexdigest()[:12], 16)


def _admin_current_etag(*, repo: MenuChoiceRepo, tenant_id: int, site_id: str, department_id: str, year: int, week: int) -> str:
    rows = repo.list_for_department_week(
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
    )
    version = _collection_version_from_rows(rows)
    return _make_coll_etag(department_id, year, week, version)


def _mirror_legacy_alt2_flag(*, site_id: str, department_id: str, year: int, week: int, weekday_num: int, choice: str) -> None:
    """Temporary compatibility mirror for legacy Alt2 readers.

    Canonical truth is written first to department_menu_choices.
    The legacy alt2_flags table is updated only as a one-way projection:
    - canonical Alt2 -> legacy Alt2 row present
    - canonical Alt1 / no explicit choice -> legacy Alt2 row absent
    """
    if int(year) != int(_current_iso_year()):
        return
    db = get_session()
    try:
        if choice == "Alt2":
            db.execute(
                text(
                    """
                    INSERT INTO alt2_flags(site_id, department_id, week, weekday, enabled)
                    VALUES(:site_id, :department_id, :week, :weekday, 1)
                    ON CONFLICT(site_id, department_id, week, weekday)
                    DO UPDATE SET enabled=excluded.enabled, version=alt2_flags.version+1, updated_at=CURRENT_TIMESTAMP
                    WHERE alt2_flags.enabled IS DISTINCT FROM excluded.enabled
                    """
                ),
                {
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "week": int(week),
                    "weekday": int(weekday_num),
                },
            )
        else:
            db.execute(
                text(
                    "DELETE FROM alt2_flags WHERE site_id=:site_id AND department_id=:department_id AND week=:week AND weekday=:weekday"
                ),
                {
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "week": int(week),
                    "weekday": int(weekday_num),
                },
            )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _make_coll_etag(department_id: str, year: int, week: int, version: int) -> str:
    return make_etag("admin", "menu-choice", f"{department_id}:{year}:{week}", version)


def _resolve_year_arg(value: str | None) -> int:
    if value is None or str(value).strip() == "":
        return _current_iso_year()
    try:
        year = int(value)
    except Exception:
        raise ValueError("invalid_year")
    if year < 2000 or year > 2100:
        raise ValueError("invalid_year")
    return year


@bp.get("/menu-choice")
@require_roles("admin", "editor")
def get_menu_choice():  # type: ignore[return-value]
    try:
        week = int(request.args.get("week", ""))
    except Exception:
        return bad_request("week query param required/int")
    if week < 1 or week > 53:
        return bad_request("Week must be between 1 and 53")
    try:
        year = _resolve_year_arg(request.args.get("year"))
    except ValueError:
        return bad_request("invalid_year")
    department_id = request.args.get("department") or request.args.get("department_id")
    if not department_id:
        return bad_request("department query param required")

    ctx = get_active_context()
    tenant_id = _tenant_id()
    try:
        site_id, _site_tenant_id = _resolve_department_scope(str(department_id), tenant_id, ctx.get("site_id"))
    except ValueError:
        return bad_request("department_not_found")
    repo = MenuChoiceRepo()
    days = repo.derive_map(
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=str(department_id),
        year=year,
        week=week,
    )
    etag = _admin_current_etag(
        repo=repo,
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=str(department_id),
        year=year,
        week=week,
    )
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
    try:
        year = _resolve_year_arg(str(data.get("year")) if data.get("year") is not None else None)
    except ValueError:
        return bad_request("invalid_year")
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
            instance="/menu-choice",
        )

    # Concurrency (If-Match)
    if_match = request.headers.get("If-Match")
    ns, kind, ident, version = parse_if_match(if_match)
    if version is None or ns != "admin" or kind != "menu-choice" or ident != f"{department_id}:{year}:{week}":
        from .http_errors import problem as _pb
        return _pb(412, "etag_mismatch", "Precondition Failed", "etag_mismatch")
    ctx = get_active_context()
    tenant_id = _tenant_id()
    try:
        site_id, _site_tenant_id = _resolve_department_scope(department_id, tenant_id, ctx.get("site_id"))
    except ValueError:
        return bad_request("department_not_found")
    repo = MenuChoiceRepo()
    current_etag = _admin_current_etag(
        repo=repo,
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
    )
    if version is None or if_match != current_etag:
        from .http_errors import problem as _pb
        cur_etag = current_etag
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

    # Canonical write first.
    repo.set_choice(
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
        weekday=weekday_num,
        selected_alt=choice,
        meal="lunch",
    )
    # Temporary compatibility mirror for legacy Alt2 readers.
    _mirror_legacy_alt2_flag(
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
        weekday_num=weekday_num,
        choice=choice,
    )
    new_etag = _admin_current_etag(
        repo=repo,
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
    )
    from flask import Response
    resp = Response(status=204)
    resp.headers["ETag"] = new_etag
    return resp


# Public alias blueprint exposing same handlers at /menu-choice (no /admin prefix)
public_bp = Blueprint("menu_choice_public", __name__)

@public_bp.get("/menu-choice")
@require_roles("admin", "editor")
def public_get_menu_choice():  # type: ignore[return-value]
    return get_menu_choice()

@public_bp.put("/menu-choice")
@require_roles("admin", "editor")
def public_put_menu_choice():  # type: ignore[return-value]
    return put_menu_choice()

__all__ = ["bp", "public_bp"]
