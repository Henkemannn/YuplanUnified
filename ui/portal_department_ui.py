from __future__ import annotations

from datetime import date as _date
from flask import Blueprint, request, render_template, current_app, g

from portal.department.auth import get_department_id_from_claims
from portal.department.service import build_department_week_payload

portal_dept_ui_bp = Blueprint("portal_dept_ui", __name__)


def _resolve_year_week(year_raw: str | None, week_raw: str | None) -> tuple[int, int]:
    if not year_raw or not week_raw:
        today = _date.today()
        y, w, _ = today.isocalendar()
        return int(y), int(w)
    try:
        year = int(year_raw)
        week = int(week_raw)
    except Exception:
        raise ValueError("invalid_year_week")
    if year < 2000 or year > 2100 or week < 1 or week > 53:
        raise ValueError("invalid_year_week")
    return year, week


@portal_dept_ui_bp.get("/ui/portal/department/week")
def portal_department_week_ui():  # type: ignore[override]
    year_raw = request.args.get("year")
    week_raw = request.args.get("week")
    demo_mode = request.args.get("demo") == "1"
    try:
        year, week = _resolve_year_week(year_raw, week_raw)
    except ValueError:
        from core.http_errors import bad_request
        return bad_request("invalid_year_or_week")

    # Demo mode: pick first department and inject fake claims; keep SQL minimal for sqlite
    if demo_mode:
        from core.db import get_session
        from sqlalchemy import text

        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments ORDER BY id LIMIT 1")).fetchone()
        finally:
            db.close()
        if not row:
            from core.http_errors import problem

            return problem(
                500,
                "demo_setup_missing",
                "Demo mode requires at least one department",
                "Run scripts/seed_demo.py to create demo data.",
            )
        demo_department_id = str(row[0])
        g.jwt_claims = {
            "department_id": demo_department_id,
            "tenant_id": 1,
            "user_id": "demo_user",
        }
        current_app.logger.info("DEMO MODE ACTIVE (department=%s)", demo_department_id)
        department_id = demo_department_id
    else:
        department_id = get_department_id_from_claims()
    payload = build_department_week_payload(department_id, year, week)
    vm = {
        "department_name": payload["department_name"],
        "site_name": payload["site_name"],
        "year": payload["year"],
        "week": payload["week"],
        "facts": payload["facts"],
        "progress": payload["progress"],
        "days": payload["days"],
        "etag_map": payload["etag_map"],
        "summary": payload.get("summary", {"registered_lunch_days": 0, "registered_dinner_days": 0}),
        "links": {
            "weekview": f"/ui/weekview?site_id={payload['site_id']}&department_id={payload['department_id']}&year={payload['year']}&week={payload['week']}",
            "report_weekview": f"/ui/reports/weekview?site_id={payload['site_id']}&year={payload['year']}&week={payload['week']}",
        },
    }
    return render_template("portal_department_week.html", vm=vm)

__all__ = ["portal_dept_ui_bp"]