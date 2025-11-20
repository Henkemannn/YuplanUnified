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
        special_totals: Dict[str, Dict[str, int]] = {"lunch": {}, "dinner": {}}
        diet_names: Dict[str, str] = {}
        for d in days:
            res = (d.get("residents") or {})
            for meal in ("lunch", "dinner"):
                try:
                    residents_total[meal] += int(res.get(meal, 0) or 0)
                except Exception:
                    pass
            diets = (d.get("diets") or {})
            for meal in ("lunch", "dinner"):
                rows = diets.get(meal) or []
                for it in rows:
                    try:
                        if bool(it.get("marked")):
                            dtid = str(it.get("diet_type_id"))
                            cnt = int(it.get("resident_count") or 0)
                            name = str(it.get("diet_name") or dtid)
                            special_totals[meal][dtid] = special_totals[meal].get(dtid, 0) + cnt
                            if dtid not in diet_names:
                                diet_names[dtid] = name
                    except Exception:
                        continue
        meals_out: Dict[str, Any] = {}
        for meal in ("lunch", "dinner"):
            specials_arr = [
                {
                    "diet_type_id": dtid,
                    "diet_name": diet_names.get(dtid, dtid),
                    "count": total,
                }
                for dtid, total in special_totals[meal].items()
                if int(total) > 0
            ]
            try:
                specials_arr.sort(key=lambda x: (-int(x.get("count", 0) or 0), str(x.get("diet_name") or "")))
            except Exception:
                pass
            total_special = sum(int(x.get("count") or 0) for x in specials_arr)
            normal = residents_total[meal] - total_special
            if normal < 0:
                normal = 0
            meals_out[meal] = {
                "residents_total": residents_total[meal],
                "special_diets": specials_arr,
                "normal_diet_count": normal,
            }
        out.append(
            {
                "department_id": dep_id,
                "department_name": dep_name,
                "meals": meals_out,
            }
        )
    return out
