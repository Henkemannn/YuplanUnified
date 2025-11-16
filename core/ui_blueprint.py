from __future__ import annotations

from flask import Blueprint, render_template, session, request, jsonify
from sqlalchemy import text

from .auth import require_roles
from .db import get_session
from .models import Note, Task, User
from .weekview.service import WeekviewService

ui_bp = Blueprint("ui", __name__, template_folder="templates", static_folder="static")

SAFE_UI_ROLES = ("superuser", "admin", "cook", "unit_portal")


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
            "site_name": site_name,
            "department_name": dep_name,
            "year": year,
            "week": week,
            "has_dinner": False,
            "days": [],
        }
        return render_template("ui/weekview.html", vm=vm)
    days = summaries[0].get("days") or []

    # Build DayVM list
    day_vms = []
    has_dinner = False
    for d in days:
        mt = d.get("menu_texts") or {}
        lunch = mt.get("lunch", {}) if isinstance(mt, dict) else {}
        dinner = mt.get("dinner", {}) if isinstance(mt, dict) else {}
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
        }
        if day_vm["dinner_alt1"] or day_vm["dinner_alt2"]:
            has_dinner = True
        day_vms.append(day_vm)

    vm = {
        "site_name": site_name,
        "department_name": dep_name,
        "year": year,
        "week": week,
        "has_dinner": has_dinner,
        "days": day_vms,
    }
    return render_template("ui/weekview.html", vm=vm)
