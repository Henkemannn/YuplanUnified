from __future__ import annotations

import uuid
from datetime import date as _date
from typing import Any

from flask import Blueprint, jsonify, request, session, make_response, current_app, g
from sqlalchemy import text

from .auth import require_roles
from .csrf import csrf_protect
from .http_errors import bad_request, not_found
from .db import get_session
from .kommun_planera_day_application import run_kommun_day_application
from .planera_product2_page3_vm import Product2Page3VmError, build_product2_page3_vm
from .planera_v2.day_context_resolver import KommunDayContextResolverError
from .weekview.cohort_completion_service import CohortWeekviewStaleError
from .weekview.cohort_bulk_completion_service import (
    CohortBulkCompletionError,
    CohortBulkCompletionTarget,
    WeekviewCohortBulkCompletionService,
)
from .weekview.repo import WeekviewRepo
from .weekview.service import WeekviewService

bp = Blueprint("planera_api", __name__, url_prefix="/api")
_service: "PlaneraService | None" = None
KITCHEN_UI_ROLES = ("kitchen", "cook", "admin", "superuser")


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


def _norm_etag_value(value: object) -> str:
    etag = str(value or "").strip()
    if not etag:
        return ""
    if "," in etag:
        etag = etag.split(",", 1)[0].strip()
    if etag.startswith("W/"):
        etag = etag[2:].strip()
    if len(etag) >= 2 and etag[0] == '"' and etag[-1] == '"':
        etag = etag[1:-1]
    return etag


def _validate_product2_site_tenant(tenant_id: int | str, site_id: str) -> bool:
    db = get_session()
    try:
        row = db.execute(text("SELECT tenant_id FROM sites WHERE id=:i"), {"i": site_id}).fetchone()
        if row is None:
            return False
        try:
            return int(row[0]) == int(tenant_id)
        except Exception:
            return False
    finally:
        db.close()


def _parse_expected_etags(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("invalid_expected_etags")
    parsed: dict[str, str] = {}
    for raw_department_id, raw_etag in payload.items():
        department_id = str(raw_department_id or "").strip()
        etag = str(raw_etag or "").strip()
        if not department_id or not etag:
            raise ValueError("invalid_expected_etags")
        parsed[department_id] = etag
    return parsed


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
    meal_labels = _meal_labels(site_id)
    mode = "shadow" if _feature_enabled("ff.planera2.shadow") else "legacy"
    try:
        payload = run_kommun_day_application(
            mode=mode,
            tenant_id=tid,
            site_id=site_id,
            service_date=date_str,
            meal_labels=meal_labels,
            department_id=department_id,
        )
    except KommunDayContextResolverError as exc:
        if exc.code in {"site_not_owned", "site_not_found", "department_scope_mismatch"}:
            return not_found("site_or_department_not_found")
        return bad_request(exc.code)
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
@require_roles("superuser", "admin", "cook", "kitchen")
@csrf_protect
def toggle_normal_exclusion():
    """Toggle a normal-mode exclusion chip for a specific day/meal/alt.

    Body JSON: {site_id, year, week, day_index, meal, alt, diet_type_id}
    Returns: {excluded: bool}
    """
    # Enforce CSRF when cross-origin is detected (double-submit policy)
    try:
        origin = request.headers.get("Origin")
        host = (request.host_url or "").rstrip("/")
        if origin and host and origin.rstrip("/") != host:
            import secrets as _secrets
            expected = session.get("CSRF_TOKEN")
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not expected or not supplied or not _secrets.compare_digest(str(expected), str(supplied)):
                resp = jsonify({
                    "type": "https://example.com/problems/csrf_invalid",
                    "title": "Forbidden",
                    "status": 403,
                    "detail": "csrf_invalid",
                })
                resp.status_code = 403
                resp.mimetype = "application/problem+json"
                return resp
    except Exception:
        pass
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


@bp.post("/planering/mark_produced_special")
@require_roles("superuser", "admin", "cook")
@csrf_protect
def mark_produced_special():
    """Bulk mark special diets as produced in weekview.

    Body JSON: {site_id, year, week, day_index, meal, diet_type_ids?: [..]}
    Returns: {ok:true, marked:{total:N}}
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
    diet_ids = payload.get("selected_diet_type_ids") or payload.get("diet_type_ids")
    if not isinstance(diet_ids, list):
        diet_ids = []
    diet_filter = {str(d) for d in diet_ids if str(d).strip()}
    if not (site_id and 0 <= day_index <= 6 and meal in ("lunch", "dinner", "dessert")):
        return bad_request("invalid_parameters")

    ok = _validate_site_and_department(site_id, None)
    if not ok:
        return not_found("site_or_department_not_found")
    _site_name, deps = ok

    from .weekview.service import WeekviewService
    from .weekview.repo import WeekviewRepo
    svc = WeekviewService()
    repo = WeekviewRepo()
    dow = int(day_index) + 1
    total_marked = 0

    for dep in deps:
        dep_id = str(dep.get("department_id"))
        payload_wv, _etag = svc.fetch_weekview(tid, year, week, dep_id, site_id=site_id)
        try:
            summaries = payload_wv.get("department_summaries") or []
            days = (summaries[0].get("days") if summaries else []) or []
        except Exception:
            days = []
        day_obj = None
        for d in days:
            try:
                if int(d.get("day_of_week")) == dow:
                    day_obj = d
                    break
            except Exception:
                continue
        if not day_obj:
            continue
        diets = ((day_obj.get("diets") or {}).get(meal)) or []
        ops = []
        for it in diets:
            try:
                dtid = str(it.get("diet_type_id"))
                cnt = int(it.get("resident_count") or 0)
            except Exception:
                continue
            if cnt <= 0:
                continue
            if diet_filter and dtid not in diet_filter:
                continue
            ops.append({"day_of_week": dow, "meal": meal, "diet_type": dtid, "marked": True})
        if ops:
            repo.apply_operations(tid, year, week, dep_id, ops)
            total_marked += len(ops)

    return jsonify({"ok": True, "marked": {"total": total_marked}})


@bp.post("/planering/clear_produced_special")
@require_roles("superuser", "admin", "cook")
@csrf_protect
def clear_produced_special():
    """Bulk clear special diet marks in weekview.

    Body JSON: {site_id, year, week, day_index, meal, diet_type_ids?: [..]}
    Returns: {ok:true, cleared:{total:N}}
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
    diet_ids = payload.get("diet_type_ids")
    if not isinstance(diet_ids, list):
        diet_ids = []
    diet_filter = {str(d) for d in diet_ids if str(d).strip()}
    if not (site_id and 0 <= day_index <= 6 and meal in ("lunch", "dinner", "dessert")):
        return bad_request("invalid_parameters")

    ok = _validate_site_and_department(site_id, None)
    if not ok:
        return not_found("site_or_department_not_found")
    _site_name, deps = ok

    from .weekview.service import WeekviewService
    from .weekview.repo import WeekviewRepo
    svc = WeekviewService()
    repo = WeekviewRepo()
    dow = int(day_index) + 1
    total_cleared = 0

    for dep in deps:
        dep_id = str(dep.get("department_id"))
        payload_wv, _etag = svc.fetch_weekview(tid, year, week, dep_id, site_id=site_id)
        try:
            summaries = payload_wv.get("department_summaries") or []
            days = (summaries[0].get("days") if summaries else []) or []
        except Exception:
            days = []
        day_obj = None
        for d in days:
            try:
                if int(d.get("day_of_week")) == dow:
                    day_obj = d
                    break
            except Exception:
                continue
        if not day_obj:
            continue
        diets = ((day_obj.get("diets") or {}).get(meal)) or []
        ops = []
        for it in diets:
            try:
                dtid = str(it.get("diet_type_id"))
                cnt = int(it.get("resident_count") or 0)
            except Exception:
                continue
            if cnt <= 0:
                continue
            if diet_filter and dtid not in diet_filter:
                continue
            ops.append({"day_of_week": dow, "meal": meal, "diet_type": dtid, "marked": False})
        if ops:
            repo.apply_operations(tid, year, week, dep_id, ops)
            total_cleared += len(ops)

    return jsonify({"ok": True, "cleared": {"total": total_cleared}})


@bp.post("/planera/product2/production-completion")
@require_roles(*KITCHEN_UI_ROLES)
@csrf_protect
def post_planera_product2_production_completion():
    tid = _tenant_id()
    if tid is None:
        return bad_request("tenant_missing")

    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        payload = {}

    site_id = str(payload.get("site_id") or "").strip()
    service_date_raw = str(payload.get("service_date") or payload.get("date") or "").strip()
    meal = str(payload.get("meal") or "").strip().lower()
    if "marked" not in payload or not isinstance(payload.get("marked"), bool):
        return bad_request("invalid_marked")
    marked = bool(payload.get("marked"))
    expected_etags_raw = payload.get("expected_etags")
    view = payload.get("view")
    special_view = payload.get("special_view")

    if not site_id or not service_date_raw or meal not in ("lunch", "dinner"):
        return bad_request("invalid_parameters")

    try:
        service_date = _date.fromisoformat(service_date_raw)
    except Exception:
        return bad_request("invalid_service_date")

    session_site_id = str(session.get("site_id") or "").strip() if "site_id" in session else ""
    if session_site_id and session_site_id != site_id:
        return jsonify({"type": "about:blank", "title": "site_mismatch", "detail": "site_mismatch"}), 403

    if not _validate_product2_site_tenant(tid, site_id):
        return not_found("site_or_department_not_found")

    try:
        vm = build_product2_page3_vm(
            tenant_id=tid,
            site_id=site_id,
            service_date=service_date,
            meal=meal,
            view=view,
            special_view=special_view,
        )
    except Product2Page3VmError:
        return not_found("site_or_department_not_found")

    if not bool(getattr(vm, "ready", False)):
        resp = jsonify(
            {
                "type": "about:blank",
                "title": "production_not_ready",
                "ready": False,
                "blockers": list(getattr(vm, "blockers", ()) or ()),
                "target_count": len(tuple(getattr(vm, "completion_targets", ()) or ())),
            }
        )
        return resp, 409

    completion_targets = tuple(getattr(vm, "completion_targets", ()) or ())
    target_department_ids = sorted({str(target.destination_id) for target in completion_targets})
    if not completion_targets:
        return (
            jsonify(
                {
                    "type": "about:blank",
                    "title": "no_completion_targets",
                    "detail": "no_completion_targets",
                    "ok": False,
                    "marked": marked,
                    "site_id": site_id,
                    "service_date": service_date.isoformat(),
                    "meal": meal,
                    "target_count": 0,
                    "departments": {},
                    "department_etags": {},
                }
            ),
            409,
        )

    try:
        expected_etags = _parse_expected_etags(expected_etags_raw)
    except ValueError:
        return bad_request("invalid_expected_etags")

    if set(expected_etags) != set(target_department_ids):
        resp = jsonify(
            {
                "type": "about:blank",
                "title": "etag_mismatch",
                "detail": "etag_mismatch",
                "expected_departments": target_department_ids,
                "provided_departments": sorted(expected_etags),
            }
        )
        return resp, 412

    weekview_service = WeekviewService()
    iso_year, iso_week, _ = service_date.isocalendar()
    current_etags: dict[str, str] = {}
    expected_base_versions: dict[str, int] = {}
    for department_id in target_department_ids:
        current_version = weekview_service.get_effective_version(tid, int(iso_year), int(iso_week), department_id, site_id)
        current_etag = weekview_service.build_etag(tid, department_id, int(iso_year), int(iso_week), current_version)
        current_etags[department_id] = current_etag
        if _norm_etag_value(expected_etags[department_id]) != _norm_etag_value(current_etag):
            resp = jsonify(
                {
                    "type": "about:blank",
                    "title": "etag_mismatch",
                    "detail": "etag_mismatch",
                    "current_etags": current_etags,
                }
            )
            return resp, 412
        expected_base_versions[department_id] = int(weekview_service.repo.get_version(tid, int(iso_year), int(iso_week), department_id))

    if not completion_targets:
        return jsonify(
            {
                "ok": True,
                "marked": marked,
                "site_id": site_id,
                "service_date": service_date.isoformat(),
                "meal": meal,
                "target_count": 0,
                "departments": {},
                "department_etags": {},
            }
        )

    bulk_service = WeekviewCohortBulkCompletionService(weekview_repo=weekview_service.repo)
    bulk_targets = [
        CohortBulkCompletionTarget(
            department_id=str(target.destination_id),
            group_id=str(target.requirement_group_id),
            service_date=_date.fromisoformat(str(target.service_date)),
            meal=str(target.meal),
        )
        for target in completion_targets
    ]
    try:
        result = bulk_service.set_marked_many_with_weekview_versions(
            tenant_id=tid,
            year=int(iso_year),
            week=int(iso_week),
            expected_base_versions=expected_base_versions,
            targets=bulk_targets,
            marked=marked,
        )
    except CohortBulkCompletionError as exc:
        return bad_request(str(exc))
    except CohortWeekviewStaleError:
        resp = jsonify(
            {
                "type": "about:blank",
                "title": "etag_mismatch",
                "detail": "etag_mismatch",
                "current_etags": current_etags,
            }
        )
        return resp, 412

    departments = {}
    department_etags = {}
    for department_id, version in sorted(result.get("departments", {}).items()):
        current_version = weekview_service.get_effective_version(tid, int(iso_year), int(iso_week), department_id, site_id)
        current_etag = weekview_service.build_etag(tid, department_id, int(iso_year), int(iso_week), current_version)
        departments[department_id] = {"version": int(version), "etag": current_etag}
        department_etags[department_id] = current_etag

    return jsonify(
        {
            "ok": True,
            "marked": marked,
            "site_id": site_id,
            "service_date": service_date.isoformat(),
            "meal": meal,
            "target_count": int(result.get("target_count") or 0),
            "departments": departments,
            "department_etags": department_etags,
        }
    )
