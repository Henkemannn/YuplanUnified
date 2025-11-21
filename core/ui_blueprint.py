from __future__ import annotations

from flask import Blueprint, render_template, session, request, jsonify
from sqlalchemy import text

from .auth import require_roles
from .db import get_session
from .models import Note, Task, User
from .weekview.service import WeekviewService
from datetime import date as _date
import uuid

ui_bp = Blueprint("ui", __name__, template_folder="templates", static_folder="static")

SAFE_UI_ROLES = ("superuser", "admin", "cook", "unit_portal")


def get_meal_labels_for_site(site_id: str | None) -> dict[str, str]:
    # Phase 1.1 default mapping (Kommun-style). TODO Phase 2: vary by site/offshore kind.
    return {"lunch": "Lunch", "dinner": "Kvällsmat"}


def _feature_enabled(name: str) -> bool:
    try:
        from flask import g, current_app
        override = getattr(g, "tenant_feature_flags", {}).get(name)
        if override is not None:
            return bool(override)
        reg = getattr(current_app, "feature_registry", None)
        if reg is not None:
            return bool(reg.enabled(name))
    except Exception:
        return False
    return False


@ui_bp.get("/workspace")
@require_roles(*SAFE_UI_ROLES)
def workspace_ui():
    tid = session.get("tenant_id")
    user_id = session.get("user_id")
    role = session.get("role")
    db = get_session()
    try:
        # Notes visibility replicates API logic
        notes_q = db.query(Note).filter(Note.tenant_id == tid)
        if role not in ("admin", "superuser"):
            notes_q = notes_q.filter((~Note.private_flag) | (Note.user_id == user_id))  # type: ignore
        notes = notes_q.order_by(Note.created_at.desc()).limit(50).all()

        tasks_q = db.query(Task).filter(Task.tenant_id == tid).order_by(Task.id.desc()).limit(50)
        # Private tasks only to creator or admin/superuser
        if role not in ("admin", "superuser"):
            tasks_q = tasks_q.filter((~Task.private_flag) | (Task.creator_user_id == user_id))  # type: ignore
        tasks = tasks_q.all()

        # Resolve assignee names map (avoid N+1 for simplicity)
        user_ids = {t.assignee_id for t in tasks if t.assignee_id}
        if user_ids:
            users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        else:
            users = {}
        # Decorate for template
        tasks_view = []
        for t in tasks:
            ass_user = users.get(t.assignee_id) if t.assignee_id else None
            tasks_view.append(
                {
                    "id": t.id,
                    "title": getattr(t, "title", None),
                    "content": getattr(t, "title", None),
                    "status": "klar" if getattr(t, "done", False) else "öppen",
                    "assignee_name": ass_user.email if ass_user else None,
                }
            )
        return render_template("ui/notes_tasks.html", notes=notes, tasks=tasks_view)
    finally:
        db.close()


@ui_bp.get("/ui/weekview")
@require_roles(*SAFE_UI_ROLES)
def weekview_ui():
    # Validate query params
    site_id = (request.args.get("site_id") or "").strip()
    department_id = (request.args.get("department_id") or "").strip()
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return jsonify({"error": "bad_request", "message": "Invalid year/week"}), 400
    if year < 2000 or year > 2100:
        return jsonify({"error": "bad_request", "message": "Invalid year"}), 400
    if week < 1 or week > 53:
        return jsonify({"error": "bad_request", "message": "Invalid week"}), 400

    # Resolve names (sites/departments)
    db = get_session()
    try:
        site_name = None
        dep_name = None
        if site_id:
            row = db.execute(text("SELECT name FROM sites WHERE id = :id"), {"id": site_id}).fetchone()
            site_name = row[0] if row else None
        if department_id:
            row = db.execute(
                text("SELECT name FROM departments WHERE id = :id"), {"id": department_id}
            ).fetchone()
            dep_name = row[0] if row else None
        if not site_name or not dep_name:
            return jsonify({"error": "not_found", "message": "Site or department not found"}), 404
    finally:
        db.close()

    # Fetch enriched weekview payload via service (no extra SQL here)
    tid = session.get("tenant_id")
    if not tid:
        return jsonify({"error": "bad_request", "message": "Missing tenant"}), 400
    svc = WeekviewService()
    payload, _etag = svc.fetch_weekview(tid, year, week, department_id)
    summaries = payload.get("department_summaries") or []
    if not summaries:
        vm = {
            "site_id": site_id,
            "department_id": department_id,
            "site_name": site_name,
            "department_name": dep_name,
            "year": year,
            "week": week,
            "has_dinner": False,
            "days": [],
        }
        return render_template("ui/weekview.html", vm=vm, meal_labels=get_meal_labels_for_site(site_id), etag=_etag)
    days = summaries[0].get("days") or []

    # Build DayVM list
    day_vms = []
    has_dinner = False
    for d in days:
        mt = d.get("menu_texts") or {}
        lunch = mt.get("lunch", {}) if isinstance(mt, dict) else {}
        dinner = mt.get("dinner", {}) if isinstance(mt, dict) else {}
        diets = d.get("diets", {}) if isinstance(d, dict) else {}
        lunch_diets = diets.get("lunch", []) if isinstance(diets, dict) else []
        dinner_diets = diets.get("dinner", []) if isinstance(diets, dict) else []
        day_vm = {
            "date": d.get("date"),
            "weekday_name": d.get("weekday_name"),
            "lunch_alt1": lunch.get("alt1"),
            "lunch_alt2": lunch.get("alt2"),
            "lunch_dessert": lunch.get("dessert"),
            "dinner_alt1": dinner.get("alt1"),
            "dinner_alt2": dinner.get("alt2"),
            "alt2_lunch": bool(d.get("alt2_lunch")),
            "residents_lunch": (d.get("residents", {}) or {}).get("lunch", 0),
            "residents_dinner": (d.get("residents", {}) or {}).get("dinner", 0),
            "lunch_diets": [
                {
                    "diet_type_id": str(x.get("diet_type_id")),
                    "diet_name": str(x.get("diet_name")),
                    "resident_count": int(x.get("resident_count", 0) or 0),
                    "marked": bool(x.get("marked")),
                }
                for x in (lunch_diets or [])
            ],
            "dinner_diets": [
                {
                    "diet_type_id": str(x.get("diet_type_id")),
                    "diet_name": str(x.get("diet_name")),
                    "resident_count": int(x.get("resident_count", 0) or 0),
                    "marked": bool(x.get("marked")),
                }
                for x in (dinner_diets or [])
            ],
        }
        if day_vm["dinner_alt1"] or day_vm["dinner_alt2"]:
            has_dinner = True
        day_vms.append(day_vm)

    vm = {
        "site_id": site_id,
        "department_id": department_id,
        "site_name": site_name,
        "department_name": dep_name,
        "year": year,
        "week": week,
        "has_dinner": has_dinner,
        "days": day_vms,
    }
    meal_labels = get_meal_labels_for_site(site_id)
    return render_template("ui/weekview.html", vm=vm, meal_labels=meal_labels, etag=_etag)


@ui_bp.get("/ui/weekview_overview")
@require_roles(*SAFE_UI_ROLES)
def weekview_overview_ui():
    # Validate query params
    site_id = (request.args.get("site_id") or "").strip()
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return jsonify({"error": "bad_request", "message": "Invalid year/week"}), 400
    if year < 2000 or year > 2100:
        return jsonify({"error": "bad_request", "message": "Invalid year"}), 400
    if week < 1 or week > 53:
        return jsonify({"error": "bad_request", "message": "Invalid week"}), 400

    # Resolve site
    db = get_session()
    try:
        row = db.execute(text("SELECT name FROM sites WHERE id = :id"), {"id": site_id}).fetchone()
        site_name = row[0] if row else None
        if not site_name:
            return jsonify({"error": "not_found", "message": "Site not found"}), 404
        # List departments for site
        deps = db.execute(
            text("SELECT id, name FROM departments WHERE site_id=:s ORDER BY name"),
            {"s": site_id},
        ).fetchall()
        departments = [(str(r[0]), str(r[1])) for r in deps]
    finally:
        db.close()

    # No departments -> empty state
    meal_labels = get_meal_labels_for_site(site_id)
    if not departments:
        vm = {
            "site_id": site_id,
            "site_name": site_name,
            "year": year,
            "week": week,
            "has_any_dinner": False,
            "departments": [],
        }
        _set_prev_next(vm)
        return render_template("ui/weekview_overview.html", vm=vm, meal_labels=meal_labels)

    # Build rows by fetching department weekviews (Phase 1: simple N calls)
    tid = session.get("tenant_id")
    if not tid:
        return jsonify({"error": "bad_request", "message": "Missing tenant"}), 400
    svc = WeekviewService()

    has_any_dinner = False
    rows = []
    for dep_id, dep_name in departments:
        payload, _etag = svc.fetch_weekview(tid, year, week, dep_id)
        summaries = payload.get("department_summaries") or []
        days = (summaries[0].get("days") if summaries else []) or []
        res_l = 0
        res_d = 0
        # Aggregate weekly diets by diet_type across all days & meals where marked
        weekly_diets_idx: dict[str, dict[str, object]] = {}
        day_vms = []
        for d in days:
            mt = d.get("menu_texts") or {}
            lunch = mt.get("lunch", {}) if isinstance(mt, dict) else {}
            dinner = mt.get("dinner", {}) if isinstance(mt, dict) else {}
            has_menu_icon = bool(
                (lunch.get("alt1") or lunch.get("alt2") or lunch.get("dessert"))
                or (dinner.get("alt1") or dinner.get("alt2"))
            )
            if dinner.get("alt1") or dinner.get("alt2"):
                has_any_dinner = True
            r = (d.get("residents") or {})
            res_l += int(r.get("lunch", 0) or 0)
            res_d += int(r.get("dinner", 0) or 0)
            # Per-day diet indicator: any marked diet in lunch or dinner
            has_marked_diets = False
            diets = d.get("diets") or {}
            for meal_key in ("lunch", "dinner"):
                rows_m = diets.get(meal_key) or []
                for it in rows_m:
                    try:
                        if bool(it.get("marked")):
                            has_marked_diets = True
                            dtid = str(it.get("diet_type_id"))
                            name = str(it.get("diet_name") or dtid)
                            cnt = int(it.get("resident_count") or 0)
                            acc = weekly_diets_idx.get(dtid)
                            if not acc:
                                weekly_diets_idx[dtid] = {
                                    "diet_type_id": dtid,
                                    "diet_name": name,
                                    "total_marked_count": cnt,
                                }
                            else:
                                acc["total_marked_count"] = int(acc["total_marked_count"]) + cnt  # type: ignore[index]
                    except Exception:
                        continue
            day_vms.append(
                {
                    "weekday_name": d.get("weekday_name"),
                    "has_menu_icon": has_menu_icon,
                    "alt2_lunch": bool(d.get("alt2_lunch")),
                    "has_marked_diets": has_marked_diets,
                    # Popup content (simple, derived values)
                    "menu": {
                        "lunch_alt1": lunch.get("alt1"),
                        "lunch_alt2": lunch.get("alt2"),
                        "lunch_dessert": lunch.get("dessert"),
                        "dinner_alt1": dinner.get("alt1"),
                        "dinner_alt2": dinner.get("alt2"),
                    },
                }
            )
        weekly_diets = list(weekly_diets_idx.values())
        try:
            weekly_diets.sort(key=lambda x: (-int(x.get("total_marked_count", 0) or 0), str(x.get("diet_name") or "")))
        except Exception:
            pass
        rows.append(
            {
                "department_id": dep_id,
                "department_name": dep_name,
                "residents_lunch_week": res_l,
                "residents_dinner_week": res_d,
                "weekly_diets": weekly_diets,
                "days": day_vms,
            }
        )

    vm = {
        "site_id": site_id,
        "site_name": site_name,
        "year": year,
        "week": week,
        "departments": rows,
        "has_any_dinner": has_any_dinner,
    }
    _set_prev_next(vm)
    return render_template("ui/weekview_overview.html", vm=vm, meal_labels=meal_labels)


@ui_bp.get("/ui/reports/weekview")
@require_roles(*SAFE_UI_ROLES)
def weekview_report_ui():  # TODO Phase 2.E.1: real aggregation; currently placeholder
    site_id = (request.args.get("site_id") or "").strip()
    department_id = (request.args.get("department_id") or "").strip() or None
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return jsonify({"error": "bad_request", "message": "Invalid year/week"}), 400
    if year < 2000 or year > 2100:
        return jsonify({"error": "bad_request", "message": "Invalid year"}), 400
    if week < 1 or week > 53:
        return jsonify({"error": "bad_request", "message": "Invalid week"}), 400
    db = get_session()
    try:
        row = db.execute(text("SELECT name FROM sites WHERE id=:i"), {"i": site_id}).fetchone()
        site_name = row[0] if row else None
        if not site_name:
            return jsonify({"error": "not_found", "message": "Site not found"}), 404
        departments: list[tuple[str, str]] = []
        if department_id:
            r = db.execute(text("SELECT id, name FROM departments WHERE id=:d AND site_id=:s"), {"d": department_id, "s": site_id}).fetchone()
            if not r:
                return jsonify({"error": "not_found", "message": "Department not found"}), 404
            departments = [(str(r[0]), str(r[1]))]
        else:
            rows = db.execute(text("SELECT id, name FROM departments WHERE site_id=:s ORDER BY name"), {"s": site_id}).fetchall()
            departments = [(str(r[0]), str(r[1])) for r in rows]
    finally:
        db.close()
    meal_labels = get_meal_labels_for_site(site_id)
    # Compute using same aggregation as API
    from .weekview_report_service import compute_weekview_report  # local import to avoid cycles
    tid = session.get("tenant_id")
    if not tid:
        return jsonify({"error": "bad_request", "message": "Missing tenant"}), 400
    dept_vms = compute_weekview_report(tid, year, week, departments)
    vm = {
        "site_id": site_id,
        "site_name": site_name,
        "department_scope": ("single" if department_id else "all"),
        "year": year,
        "week": week,
        "departments": dept_vms,
    }
    return render_template("ui/weekview_report.html", vm=vm, meal_labels=meal_labels)


@ui_bp.get("/ui/planera/day")
@require_roles(*SAFE_UI_ROLES)
def planera_day_ui():
    if not _feature_enabled("ff.planera.enabled"):
        return render_template("ui/planera_day.html", vm={"error": "planera_disabled"})
    site_id = (request.args.get("site_id") or "").strip()
    date_str = (request.args.get("date") or "").strip()
    department_id = (request.args.get("department_id") or "").strip() or None
    if not site_id or not date_str:
        return render_template("ui/planera_day.html", vm={"error": "invalid_parameters"})
    try:
        uuid.UUID(site_id)
        if department_id:
            uuid.UUID(department_id)
        _date.fromisoformat(date_str)
    except Exception:
        return render_template("ui/planera_day.html", vm={"error": "invalid_parameters"})
    db = get_session()
    try:
        row = db.execute(text("SELECT name FROM sites WHERE id=:i"), {"i": site_id}).fetchone()
        site_name = row[0] if row else None
        if not site_name:
            return render_template("ui/planera_day.html", vm={"error": "not_found"})
        deps_q = "SELECT id, name FROM departments WHERE site_id=:s"
        params = {"s": site_id}
        if department_id:
            deps_q += " AND id=:d"
            params["d"] = department_id
        rows = db.execute(text(deps_q), params).fetchall()
        if department_id and not rows:
            return render_template("ui/planera_day.html", vm={"error": "not_found"})
        from .planera_service import PlaneraService
        svc = PlaneraService()
        agg = svc.compute_day(
            session.get("tenant_id", 0),
            site_id,
            date_str,
            [(str(r[0]), str(r[1])) for r in rows],
        )
        departments = agg["departments"]
        totals = agg["totals"]
    finally:
        db.close()
    vm = {
        "site_id": site_id,
        "site_name": site_name,
        "date": date_str,
        "departments": departments,
        "totals": totals,
    }
    return render_template("ui/planera_day.html", vm=vm, meal_labels=get_meal_labels_for_site(site_id))


@ui_bp.get("/ui/planera/week")
@require_roles(*SAFE_UI_ROLES)
def planera_week_ui():
    if not _feature_enabled("ff.planera.enabled"):
        return render_template("ui/planera_week.html", vm={"error": "planera_disabled"})
    site_id = (request.args.get("site_id") or "").strip()
    try:
        year = int(request.args.get("year", ""))
        week = int(request.args.get("week", ""))
    except Exception:
        return render_template("ui/planera_week.html", vm={"error": "invalid_parameters"})
    department_id = (request.args.get("department_id") or "").strip() or None
    if not site_id or year < 2000 or year > 2100 or week < 1 or week > 53:
        return render_template("ui/planera_week.html", vm={"error": "invalid_parameters"})
    try:
        uuid.UUID(site_id)
        if department_id:
            uuid.UUID(department_id)
    except Exception:
        return render_template("ui/planera_week.html", vm={"error": "invalid_parameters"})
    db = get_session()
    try:
        row = db.execute(text("SELECT name FROM sites WHERE id=:i"), {"i": site_id}).fetchone()
        site_name = row[0] if row else None
        if not site_name:
            return render_template("ui/planera_week.html", vm={"error": "not_found"})
    finally:
        db.close()
    from .planera_service import PlaneraService
    svc = PlaneraService()
    agg = svc.compute_week(
        session.get("tenant_id", 0),
        site_id,
        year,
        week,
        [],  # TODO(P1.1.1): support optional department filter for week UI similar to API
    )
    days = agg["days"]
    vm = {
        "site_id": site_id,
        "site_name": site_name,
        "year": year,
        "week": week,
        "days": days,
    }
    return render_template("ui/planera_week.html", vm=vm, meal_labels=get_meal_labels_for_site(site_id))


def _set_prev_next(vm: dict) -> None:
    # Compute prev/next week for navigation
    y = int(vm["year"])
    w = int(vm["week"])
    # Prev
    if w > 1:
        prev_w = w - 1
        prev_y = y
    else:
        prev_w = 53
        prev_y = y - 1
    # Next
    if w < 53:
        next_w = w + 1
        next_y = y
    else:
        next_w = 1
        next_y = y + 1
    vm["prev_week"] = {"year": prev_y, "week": prev_w}
    vm["next_week"] = {"year": next_y, "week": next_w}
