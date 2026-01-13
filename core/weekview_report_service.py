from __future__ import annotations

from typing import Iterable, Tuple, List, Dict, Any

from .weekview.service import WeekviewService
from .admin_repo import DietDefaultsRepo


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
        marks_raw = (summaries[0].get("marks") if summaries else []) or []
        # Build mark index: (dow, meal, diet_type_id)
        marked_idx: set[tuple[int, str, str]] = set()
        try:
            for m in marks_raw:
                if bool(m.get("marked")):
                    marked_idx.add((int(m.get("day_of_week")), str(m.get("meal")), str(m.get("diet_type"))))
        except Exception:
            marked_idx = set()
        # Planned defaults and always_mark flags per department
        defaults_items = DietDefaultsRepo().list_for_department(dep_id)
        planned_map: Dict[str, int] = {str(it["diet_type_id"]): int(it.get("default_count", 0)) for it in defaults_items}
        always_map: Dict[str, bool] = {str(it["diet_type_id"]): bool(it.get("always_mark", False)) for it in defaults_items}
        # Accumulators
        residents_total = {"lunch": 0, "dinner": 0}
        debiterbar_total = {"lunch": 0, "dinner": 0}
        diet_names: Dict[str, str] = {}
        day_rows: List[Dict[str, Any]] = []
        for d in days:
            res = (d.get("residents") or {})
            for meal in ("lunch", "dinner"):
                try:
                    residents_total[meal] += int(res.get(meal, 0) or 0)
                except Exception:
                    pass
            # Compute debiterbar specialkost for the day per meal
            dow = int(d.get("day_of_week") or 0)
            for meal in ("lunch", "dinner"):
                deb_day = 0
                for dtid, planned_cnt in planned_map.items():
                    if planned_cnt <= 0:
                        continue
                    if always_map.get(dtid) or ((dow, meal, dtid) in marked_idx):
                        deb_day += planned_cnt
                debiterbar_total[meal] += deb_day
                # Collect day row once
            day_rows.append(
                {
                    "weekday_name": d.get("weekday_name"),
                    "lunch_residents": int(res.get("lunch", 0) or 0),
                    "dinner_residents": int(res.get("dinner", 0) or 0),
                    "lunch_debiterbar": sum(
                        planned_map.get(dt, 0)
                        for dt in planned_map.keys()
                        if planned_map.get(dt, 0) > 0 and (always_map.get(dt) or ((dow, "lunch", dt) in marked_idx))
                    ),
                    "dinner_debiterbar": sum(
                        planned_map.get(dt, 0)
                        for dt in planned_map.keys()
                        if planned_map.get(dt, 0) > 0 and (always_map.get(dt) or ((dow, "dinner", dt) in marked_idx))
                    ),
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
                # Phase 3: debiterbar specialkost totals based on marks + always_mark
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
