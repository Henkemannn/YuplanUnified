from __future__ import annotations

import uuid
from datetime import date as _date
from typing import Any

from flask import Blueprint, jsonify, request, session, make_response, current_app, g

from .auth import require_roles
from .http_errors import bad_request, not_found
from .db import get_session

bp = Blueprint("planera_api", __name__, url_prefix="/api")
_service: "PlaneraService | None" = None


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


def _require_planera_enabled():
    if not _feature_enabled("ff.planera.enabled"):
        return not_found("planera_disabled")
    return None


def _tenant_id() -> Any:
    tid = session.get("tenant_id")
    if not tid:
        return None
    return tid


def _build_etag(kind: str, payload: dict) -> str:
    import json, hashlib
    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception:
        canonical = kind
    h = hashlib.sha1(canonical.encode()).hexdigest()[:16]
    return f'W/"planera:{kind}:{h}"'


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


def _ensure_normal_exclusions_schema() -> None:
    """Create normal_exclusions table in SQLite/testing environments.

    In production (Postgres), Alembic should manage migrations; here we guard
    with a dialect check and only create in SQLite to keep tests passing.
    """
    db = get_session()
    try:
        dialect = db.bind.dialect.name if db.bind is not None else ""
        if dialect != "sqlite":
            return
        db.execute(
            __import__("sqlalchemy").text(
                """
                CREATE TABLE IF NOT EXISTS normal_exclusions (
                  tenant_id TEXT NOT NULL,
                  site_id TEXT NOT NULL,
                  year INTEGER NOT NULL,
                  week INTEGER NOT NULL,
                  day_index INTEGER NOT NULL,
                  meal TEXT NOT NULL,
                  alt TEXT NOT NULL,
                  diet_type_id TEXT NOT NULL,
                  UNIQUE (tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
                );
                """
            )
        )
        db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass


@bp.get("/planera/day")
@require_roles("admin", "editor", "viewer")
def get_planera_day():
    maybe = _require_planera_enabled()
    if maybe is not None:
        return maybe
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
    global _service
    if _service is None:
        from .planera_service import PlaneraService
        _service = PlaneraService()
    meal_labels = _meal_labels(site_id)
    agg = _service.compute_day(tid, site_id, date_str, [(d["department_id"], d["department_name"]) for d in deps])
    payload = {
        "site_id": site_id,
        "site_name": site_name,
        "date": date_str,
        "meal_labels": meal_labels,
        "departments": agg["departments"],
        "totals": agg["totals"],
    }
    etag = _build_etag("day", payload)
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
    maybe = _require_planera_enabled()
    if maybe is not None:
        return maybe
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
    global _service
    if _service is None:
        from .planera_service import PlaneraService
        _service = PlaneraService()
    meal_labels = _meal_labels(site_id)
    agg = _service.compute_week(tid, site_id, year, week, [(d["department_id"], d["department_name"]) for d in deps])
    payload = {
        "site_id": site_id,
        "site_name": site_name,
        "year": year,
        "week": week,
        "meal_labels": meal_labels,
        "days": agg["days"],
        "weekly_totals": agg["weekly_totals"],
    }
    etag = _build_etag("week", payload)
    maybe = _conditional(etag)
    if maybe is not None:
        return maybe
    resp = jsonify(payload)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp


@bp.get("/planera/week/csv")
@require_roles("admin", "editor", "viewer")
def get_planera_week_csv():  # CSV export for week aggregation
    maybe = _require_planera_enabled()
    if maybe is not None:
        return maybe
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
    global _service
    if _service is None:
        from .planera_service import PlaneraService
        _service = PlaneraService()
    agg = _service.compute_week(tid, site_id, year, week, [(d["department_id"], d["department_name"]) for d in deps])
    payload_for_etag = {
        "site_id": site_id,
        "site_name": site_name,
        "year": year,
        "week": week,
        "days": agg["days"],
        "weekly_totals": agg["weekly_totals"],
    }
    etag = _build_etag("week", payload_for_etag)
    inm = request.headers.get("If-None-Match")
    if inm and inm == etag:
        resp = make_response("")
        resp.status_code = 304
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    # Build CSV rows
    import csv, io
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["date", "weekday", "meal", "department", "residents_total", "normal", "special_diets"])
    # For department resolution we iterate departments again and fetch per department days for precise per-dept counts
    # However agg["days"] already aggregates across all departments. For CSV we output aggregated totals per day+meal per department separately.
    # Simplification: output aggregated site totals only (department column = "__total__") plus per-day site totals.
    # Future enhancement: expand per department rows.
    weekday_map = {d["day_of_week"]: d["weekday_name"] for d in agg["days"]}
    for d in agg["days"]:
        dow = d.get("day_of_week")
        date_str = d.get("date")
        weekday_name = d.get("weekday_name")
        for meal_key in ("lunch", "dinner"):
            meal = (d.get("meals") or {}).get(meal_key, {})
            specials = meal.get("special_diets") or []
            specials_str = ";".join(f"{s.get('diet_name')}:{int(s.get('count') or 0)}" for s in specials) if specials else ""
            w.writerow([
                date_str,
                weekday_name,
                meal_key,
                "__total__",
                int(meal.get("residents_total") or 0),
                int(meal.get("normal_diet_count") or 0),
                specials_str,
            ])
    csv_text = output.getvalue()
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return resp


@bp.post("/kitchen/planering/normal_exclusions/toggle")
@require_roles("admin", "editor", "viewer")
def toggle_normal_exclusion():
    """Toggle a normal-mode exclusion chip for a specific day/meal/alt.

    Body JSON: {site_id, year, week, day_index, meal, alt, diet_type_id}
    Returns: {excluded: bool}
    """
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        payload = {}
    site_id = str(payload.get("site_id") or "").strip()
    try:
        year = int(payload.get("year"))
        week = int(payload.get("week"))
        day_index = int(payload.get("day_index"))
    except Exception:
        return bad_request("invalid_parameters")
    meal = str(payload.get("meal") or "").strip().lower()
    alt = str(payload.get("alt") or "").strip()
    diet_type_id = str(payload.get("diet_type_id") or "").strip()
    if not (site_id and diet_type_id and alt in ("1", "2") and meal in ("lunch", "dinner", "dessert") and 0 <= day_index <= 6):
        return bad_request("invalid_parameters")

    # Ensure table in SQLite
    try:
        _ensure_normal_exclusions_schema()
    except Exception:
        pass

    db = get_session()
    try:
        # Check if row exists
        row = db.execute(
            __import__("sqlalchemy").text(
                """
                SELECT 1 FROM normal_exclusions
                WHERE tenant_id=:tid AND site_id=:s AND year=:y AND week=:w
                  AND day_index=:d AND meal=:m AND alt=:a AND diet_type_id=:dt
                LIMIT 1
                """
            ),
            {"tid": str(tid), "s": site_id, "y": year, "w": week, "d": day_index, "m": meal, "a": alt, "dt": diet_type_id},
        ).fetchone()
        if row:
            # Remove existing exclusion
            db.execute(
                __import__("sqlalchemy").text(
                    """
                    DELETE FROM normal_exclusions
                    WHERE tenant_id=:tid AND site_id=:s AND year=:y AND week=:w
                      AND day_index=:d AND meal=:m AND alt=:a AND diet_type_id=:dt
                    """
                ),
                {"tid": str(tid), "s": site_id, "y": year, "w": week, "d": day_index, "m": meal, "a": alt, "dt": diet_type_id},
            )
            db.commit()
            return jsonify({"excluded": False})
        else:
            # Insert new exclusion
            db.execute(
                __import__("sqlalchemy").text(
                    """
                    INSERT INTO normal_exclusions(tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
                    VALUES (:tid, :s, :y, :w, :d, :m, :a, :dt)
                    """
                ),
                {"tid": str(tid), "s": site_id, "y": year, "w": week, "d": day_index, "m": meal, "a": alt, "dt": diet_type_id},
            )
            db.commit()
            return jsonify({"excluded": True})
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return bad_request("toggle_failed")
    finally:
        try:
            db.close()
        except Exception:
            pass
