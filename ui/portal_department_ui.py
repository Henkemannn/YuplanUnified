from __future__ import annotations

from datetime import date as _date, timedelta
from flask import Blueprint, request, render_template, current_app, url_for

from portal.department.auth import DepartmentPortalScope, resolve_department_portal_scope
from portal.department.home_service import build_department_home_payload
from portal.department.service import build_department_week_payload

portal_dept_ui_bp = Blueprint("portal_dept_ui", __name__)

_SV_MONTHS = {
    1: "januari",
    2: "februari",
    3: "mars",
    4: "april",
    5: "maj",
    6: "juni",
    7: "juli",
    8: "augusti",
    9: "september",
    10: "oktober",
    11: "november",
    12: "december",
}


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


def _format_sv_date_span(start_date: _date, end_date: _date) -> str:
    if start_date.year == end_date.year and start_date.month == end_date.month:
        return f"{start_date.day}–{end_date.day} {_SV_MONTHS[start_date.month]} {start_date.year}"
    if start_date.year == end_date.year:
        return (
            f"{start_date.day} {_SV_MONTHS[start_date.month]}–"
            f"{end_date.day} {_SV_MONTHS[end_date.month]} {start_date.year}"
        )
    return (
        f"{start_date.day} {_SV_MONTHS[start_date.month]} {start_date.year}–"
        f"{end_date.day} {_SV_MONTHS[end_date.month]} {end_date.year}"
    )


def _format_sv_short_date(day: _date) -> str:
    return f"{day.day} {_SV_MONTHS[day.month][:3]}"


def _portal_home_url(scope: DepartmentPortalScope) -> str:
    if scope.role == "unit_portal":
        return url_for("portal_dept_ui.portal_department_home_ui")
    return url_for("portal_dept_ui.portal_department_home_ui", department_id=scope.department_id)


def _portal_week_url(year: int, week: int, department_id: str | None = None) -> str:
    if department_id:
        return url_for("portal_dept_ui.portal_department_week_ui", year=year, week=week, department_id=department_id)
    return url_for("portal_dept_ui.portal_department_week_ui", year=year, week=week)


def _shift_iso_week(year: int, week: int, delta_weeks: int) -> tuple[int, int]:
    week_start = _date.fromisocalendar(year, week, 1)
    shifted = week_start + timedelta(days=7 * delta_weeks)
    shifted_year, shifted_week, _ = shifted.isocalendar()
    return int(shifted_year), int(shifted_week)


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
    home_payload = build_department_home_payload(scope)
    payload = build_department_week_payload(scope, year, week)
    for day in payload["days"]:
        day_date = _date.fromisoformat(day["date"])
        day["short_date_label"] = _format_sv_short_date(day_date)
    week_start = _date.fromisoformat(payload["days"][0]["date"])
    week_end = _date.fromisoformat(payload["days"][-1]["date"])
    week_span_label = _format_sv_date_span(week_start, week_end)
    contextual_department_id = (request.args.get("department_id") or "").strip() or None
    if scope.role == "unit_portal":
        contextual_department_id = None
    week_options: list[dict[str, object]] = []
    selected_week_key = f"{year}-{week}"
    for option in home_payload.get("weeks", []):
        option_year = int(option.get("year") or 0)
        option_week = int(option.get("week") or 0)
        option_url = _portal_week_url(option_year, option_week, contextual_department_id)
        week_options.append(
            {
                "year": option_year,
                "week": option_week,
                "label": f"Vecka {option_week} · {option.get('span', '')} {option_year}",
                "url": option_url,
                "selected": f"{option_year}-{option_week}" == selected_week_key,
            }
        )
    if not any(option["selected"] for option in week_options):
        week_options.insert(
            0,
            {
                "year": year,
                "week": week,
                "label": f"Vecka {week} · {week_span_label}",
                "url": _portal_week_url(year, week, contextual_department_id),
                "selected": True,
            },
        )
    required_choice_count = sum(1 for day in payload["days"] if day["menu"].get("lunch_alt1") and day["menu"].get("lunch_alt2"))
    completed_choice_count = sum(
        1
        for day in payload["days"]
        if day["menu"].get("lunch_alt1")
        and day["menu"].get("lunch_alt2")
        and day["choice"].get("selected_alt") in {"Alt1", "Alt2"}
    )
    vm = {
        "department_name": payload["department_name"],
        "site_name": payload["site_name"],
        "year": payload["year"],
        "week": payload["week"],
        "week_span_label": week_span_label,
        "facts": payload["facts"],
        "progress": payload["progress"],
        "choice_progress": {
            "required": required_choice_count,
            "completed": completed_choice_count,
        },
        "days": payload["days"],
        "etag_map": payload["etag_map"],
        "summary": payload.get("summary", {"registered_lunch_days": 0, "registered_dinner_days": 0}),
        "week_selector_label": f"Vecka {week} · {week_span_label}",
    }
    portal_home_url = _portal_home_url(scope)
    return render_template(
        "portal_department_week.html",
        vm=vm,
        portal_home_url=portal_home_url,
        portal_week_change_url=(
            f"/portal/department/menu-choice/change?department_id={contextual_department_id}"
            if contextual_department_id
            else "/portal/department/menu-choice/change"
        ),
        portal_week_status_url=(
            f"/portal/department/week/status?year={year}&week={week}&department_id={contextual_department_id}"
            if contextual_department_id
            else f"/portal/department/week/status?year={year}&week={week}"
        ),
        portal_week_submit_url=(
            f"/portal/department/week/submit?department_id={contextual_department_id}"
            if contextual_department_id
            else "/portal/department/week/submit"
        ),
        portal_week_options=week_options,
        nav_context="portal_department",
        hide_sidebar=True,
        portal_compact_footer=True,
    )


@portal_dept_ui_bp.get("/ui/portal/department")
def portal_department_home_ui():  # type: ignore[override]
    explicit_department_id = (request.args.get("department_id") or "").strip() or None
    scope = resolve_department_portal_scope(explicit_department_id=explicit_department_id)
    vm = build_department_home_payload(scope)
    if explicit_department_id and scope.role != "unit_portal":
        for week in vm.get("weeks", []):
            week["url"] = _portal_week_url(int(week["year"]), int(week["week"]), explicit_department_id)
    portal_home_url = _portal_home_url(scope)
    return render_template(
        "portal_department_home.html",
        vm=vm,
        portal_home_url=portal_home_url,
        nav_context="portal_department",
        hide_sidebar=True,
        portal_compact_footer=True,
    )

__all__ = ["portal_dept_ui_bp"]