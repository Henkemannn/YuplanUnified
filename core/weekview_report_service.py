from __future__ import annotations

from typing import Iterable, Tuple, List, Dict, Any

from .weekview.service import WeekviewService


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
            diets_by_meal = d.get("diets") or {}
            day_debiterbar: Dict[str, int] = {"lunch": 0, "dinner": 0}
            for meal in ("lunch", "dinner"):
                diets = (diets_by_meal.get(meal) or []) if isinstance(diets_by_meal, dict) else []
                deb_day = 0
                for diet in diets:
                    if bool(diet.get("marked")):
                        try:
                            deb_day += int(diet.get("resident_count") or 0)
                        except Exception:
                            continue
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
