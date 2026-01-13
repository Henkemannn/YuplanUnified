from __future__ import annotations

from flask import Blueprint, request, jsonify, session
from sqlalchemy import text

from .auth import require_roles
from .db import get_session
from .ui_blueprint import SAFE_UI_ROLES, get_meal_labels_for_site
from .weekview_report_service import compute_weekview_report

bp = Blueprint("weekview_report", __name__)


@bp.get("/api/reports/weekview")
@require_roles(*SAFE_UI_ROLES)
def weekview_report_api():  # TODO Phase 2.E.1: implement real aggregation per docs/weekview_report_phase2e.md
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

    department_id = (request.args.get("department_id") or "").strip() or None

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
    tid = session.get("tenant_id")
    if not tid:
        return jsonify({"error": "bad_request", "message": "Missing tenant"}), 400
    dept_payload = compute_weekview_report(tid, year, week, departments)

    payload = {
        "site_id": site_id,
        "site_name": site_name,
        "year": year,
        "week": week,
        "meal_labels": meal_labels,
        "departments": dept_payload,
    }
    return jsonify(payload)
