from __future__ import annotations

from datetime import date as _date
from flask import Blueprint, request, render_template, current_app

from portal.department.auth import DepartmentPortalScope, resolve_department_portal_scope
from portal.department.service import build_department_week_payload

portal_dept_ui_bp = Blueprint("portal_dept_ui", __name__)


def _is_pilot_or_prod() -> bool:
    env = (current_app.config.get("DEPLOY_ENV") or current_app.config.get("APP_ENV") or "").lower()
    if not env:
        import os

        env = (os.getenv("DEPLOY_ENV") or os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
    return env in ("pilot", "prod", "production")


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
    if demo_mode and _is_pilot_or_prod():
        from flask import abort

        abort(404)
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
            row = db.execute(
                text("SELECT d.id, d.site_id, s.tenant_id FROM departments d LEFT JOIN sites s ON s.id = d.site_id ORDER BY d.id LIMIT 1")
            ).fetchone()
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
        demo_site_id = str(row[1])
        demo_tenant_id = int(row[2] or 1)
        current_app.logger.info("DEMO MODE ACTIVE (department=%s)", demo_department_id)
        scope = DepartmentPortalScope(
            user_id=0,
            role="demo",
            tenant_id=demo_tenant_id,
            department_id=demo_department_id,
            site_id=demo_site_id,
        )
    else:
        scope = resolve_department_portal_scope()
    payload = build_department_week_payload(scope, year, week)
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