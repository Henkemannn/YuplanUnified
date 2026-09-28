from __future__ import annotations

from datetime import date as _date
from typing import Iterable, Tuple, List, Dict, Any

from sqlalchemy import text

from .db import get_session
from .department_requirement_group_repo import DepartmentRequirementGroupsRepo
from .department_requirement_group_weekview_projection import build_department_requirement_group_weekview_projection
from .weekview.service import WeekviewService


def _normalize_service_date(value: Any) -> _date:
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("service_date_invalid")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:
        raise ValueError("service_date_invalid") from exc


def _resolve_department_site_id(department_id: str, site_id: str | None = None) -> str:
    resolved_site_id = str(site_id or "").strip()
    if resolved_site_id:
        return resolved_site_id
    db = get_session()
    try:
        row = db.execute(text("SELECT site_id FROM departments WHERE id=:dep"), {"dep": str(department_id)}).fetchone()
        return str(row[0]) if row and row[0] is not None else ""
    finally:
        db.close()


def _legacy_specialkost_count_from_day(day: dict[str, Any], meal_key: str) -> int:
    diets_by_meal = day.get("diets") or {}
    diets = (diets_by_meal.get(meal_key) or []) if isinstance(diets_by_meal, dict) else []
    total = 0
    for diet in diets:
        if not bool(diet.get("marked")):
            continue
        name = str(diet.get("diet_name", "")).lower()
        diet_type_id = str(diet.get("diet_type_id", "")).lower()
        if name in ("normal", "normalkost") or diet_type_id in ("normal", "normalkost"):
            continue
        try:
            total += int(diet.get("resident_count") or 0)
        except Exception:
            continue
    return total


def resolve_weekview_specialkost_count(
    tenant_id: int | str,
    site_id: str | None,
    department_id: str,
    service_date: Any,
    meal: Any,
    *,
    weekview_day: dict[str, Any] | None = None,
) -> int:
    normalized_date = _normalize_service_date(service_date)
    meal_key = str(meal or "").strip().lower()
    if meal_key not in {"lunch", "dinner"}:
        raise ValueError("meal_key_invalid")

    if DepartmentRequirementGroupsRepo().list_for_department(str(department_id)):
        resolved_site_id = _resolve_department_site_id(str(department_id), site_id)
        if not resolved_site_id:
            raise ValueError("site_id_missing")
        projection = build_department_requirement_group_weekview_projection(
            tenant_id=tenant_id,
            site_id=resolved_site_id,
            department_id=str(department_id),
            service_date=normalized_date,
            meal_key=meal_key,
        )
        return sum(int(need.effective_quantity) for need in projection.needs if bool(need.marked))

    if weekview_day is None:
        iso_year, iso_week, _ = normalized_date.isocalendar()
        payload, _etag = WeekviewService().fetch_weekview(
            tenant_id,
            iso_year,
            iso_week,
            str(department_id),
            _resolve_department_site_id(str(department_id), site_id) or None,
        )
        summaries = payload.get("department_summaries") or []
        days = (summaries[0].get("days") if summaries else []) or []
        weekview_day = next((day for day in days if str(day.get("date")) == normalized_date.isoformat()), {})

    return _legacy_specialkost_count_from_day(dict(weekview_day or {}), meal_key)


def compute_weekview_report(
    tenant_id: int | str,
    year: int,
    week: int,
    departments: Iterable[Tuple[str, str]],
) -> List[Dict[str, Any]]:
    """
    Build weekly report per department using WeekviewService-enriched days.

    Returns list of {department_id, department_name, meals:{lunch: {...}, dinner: {...}}}
    where each meal has residents_total, special_diets[], normal_diet_count.
    """
    svc = WeekviewService()
    out: List[Dict[str, Any]] = []
    for dep_id, dep_name in departments:
        payload, _etag = svc.fetch_weekview(tenant_id, year, week, dep_id)
        summaries = payload.get("department_summaries") or []
        days = (summaries[0].get("days") if summaries else []) or []
        # Accumulators
        residents_total = {"lunch": 0, "dinner": 0}
        debiterbar_total = {"lunch": 0, "dinner": 0}
        day_rows: List[Dict[str, Any]] = []
        for d in days:
            res = (d.get("residents") or {})
            for meal in ("lunch", "dinner"):
                try:
                    residents_total[meal] += int(res.get(meal, 0) or 0)
                except Exception:
                    pass
            day_debiterbar: Dict[str, int] = {"lunch": 0, "dinner": 0}
            for meal in ("lunch", "dinner"):
                deb_day = resolve_weekview_specialkost_count(
                    tenant_id,
                    None,
                    dep_id,
                    d.get("date"),
                    meal,
                    weekview_day=d,
                )
                day_debiterbar[meal] = deb_day
                debiterbar_total[meal] += deb_day
            day_rows.append(
                {
                    "weekday_name": d.get("weekday_name"),
                    "lunch_residents": int(res.get("lunch", 0) or 0),
                    "dinner_residents": int(res.get("dinner", 0) or 0),
                    "lunch_debiterbar": day_debiterbar["lunch"],
                    "dinner_debiterbar": day_debiterbar["dinner"],
                }
            )
        meals_out: Dict[str, Any] = {}
        for meal in ("lunch", "dinner"):
            total_deb = int(debiterbar_total[meal] or 0)
            normal = residents_total[meal] - total_deb
            if normal < 0:
                normal = 0
            meals_out[meal] = {
                "residents_total": residents_total[meal],
                # Phase 3: debiterbar specialkost totals based on enriched Weekview marks
                "debiterbar_specialkost_count": total_deb,
                "normal_diet_count": normal,
            }
        out.append(
            {
                "department_id": dep_id,
                "department_name": dep_name,
                "meals": meals_out,
                "days": day_rows,
            }
        )
    return out
