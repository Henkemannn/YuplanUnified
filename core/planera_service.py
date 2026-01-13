from __future__ import annotations

from datetime import date as _date
from typing import Any, Iterable, List, Dict, Tuple

from .weekview.service import WeekviewService


class PlaneraService:
    """Aggregation logic for Planera Phase P1.1.

    Builds read-only diet/resident summaries per day or week using WeekviewService.
    """

    def __init__(self, weekview: WeekviewService | None = None) -> None:
        self._weekview = weekview or WeekviewService()

    # =============================
    # Phase 2: Day/Meal plan overview
    # =============================
    def get_plan_view(self, tenant_id: int, site_id: str, date: _date, meal: str, department_id: str | None = None) -> Dict[str, Any]:
        year, week, _ = date.isocalendar()
        # List departments for the site and resolve site name
        from sqlalchemy import text
        from .db import get_session
        db = get_session()
        try:
            dep_rows = db.execute(text("SELECT id, name FROM departments WHERE site_id=:s"), {"s": site_id}).fetchall()
            # If a specific department_id is provided, ensure it's included
            if department_id:
                row = db.execute(text("SELECT id, name FROM departments WHERE id=:d"), {"d": department_id}).fetchone()
                if row:
                    dep_rows = dep_rows + [row]
            site_row = db.execute(text("SELECT name FROM sites WHERE id=:i"), {"i": site_id}).fetchone()
        finally:
            db.close()
        departments: List[Tuple[str, str]] = []
        seen: set[str] = set()
        for r in dep_rows:
            rid = str(r[0]); rn = str(r[1])
            if rid in seen:
                continue
            seen.add(rid)
            departments.append((rid, rn))
        site_name = site_row[0] if site_row else "Site"
        # Compute per-department meal payloads using existing Phase 1 logic
        day_vm = self.compute_day(tenant_id, site_id, date.isoformat(), departments)
        dep_payloads: Dict[str, Dict[str, Any]] = {d["department_id"]: d for d in day_vm.get("departments", [])}
        # Pull registrations to reflect "Klar" status
        from .meal_registration_repo import MealRegistrationRepo
        reg_repo = MealRegistrationRepo()
        reg_repo.ensure_table_exists()
        is_done_map: Dict[Tuple[str, str], bool] = {}
        for dep_id, _dep_name in departments:
            reg_list = reg_repo.get_registrations_for_week(tenant_id, site_id, dep_id, year, week)
            # Index by (date, meal)
            idx = {(str(it["date"]), str(it["meal_type"])): bool(it["registered"]) for it in reg_list}
            is_done_map[(dep_id, date.isoformat())] = bool(idx.get((date.isoformat(), meal)))
        # Build rows
        rows: List[Dict[str, Any]] = []
        totals_normalkost = 0
        totals_specials_acc: Dict[str, int] = {}
        for dep_id, dep_name in departments:
            dep = dep_payloads.get(dep_id) or {}
            meals = dep.get("meals", {})
            m = meals.get(meal, {}) if isinstance(meals, dict) else {}
            residents_total = int(m.get("residents_total") or 0)
            specials_arr = m.get("special_diets") or []
            specials_map: Dict[str, int] = {}
            for it in specials_arr:
                nm = str(it.get("diet_name") or "")
                cnt = int(it.get("count") or 0)
                if nm and cnt > 0:
                    specials_map[nm] = specials_map.get(nm, 0) + cnt
                    totals_specials_acc[nm] = totals_specials_acc.get(nm, 0) + cnt
            normal_cnt = int(m.get("normal_diet_count") or 0)
            totals_normalkost += normal_cnt
            rows.append({
                "department_id": dep_id,
                "department_name": dep_name or "Avdelning",
                "residents_count": residents_total,
                "specials": specials_map,
                "is_done": bool(is_done_map.get((dep_id, date.isoformat()))),
            })
        return {
            "date": date,
            "meal": meal,
            "site_name": site_name,
            "rows": rows,
            "totals_normalkost": totals_normalkost,
            "totals_specials": totals_specials_acc,
        }

    def mark_done(self, tenant_id: int, site_id: str, date: _date, meal: str, department_ids: List[str]) -> None:
        from .meal_registration_repo import MealRegistrationRepo
        repo = MealRegistrationRepo()
        repo.ensure_table_exists()
        for dep_id in department_ids:
            repo.upsert_registration(tenant_id=tenant_id, site_id=site_id, department_id=dep_id, date_str=date.isoformat(), meal_type=meal, registered=True)

    def compute_day(
        self,
        tenant_id: int | str,
        site_id: str,  # retained for future site-specific logic
        iso_date: str,
        departments: Iterable[Tuple[str, str]],
    ) -> Dict[str, Any]:
        try:
            d_obj = _date.fromisoformat(iso_date)
            year, week, _dow = d_obj.isocalendar()
        except Exception:
            year, week = 1970, 1
        dep_out: List[Dict[str, Any]] = []
        total_special_acc: Dict[str, Dict[str, int]] = {"lunch": {}, "dinner": {}}
        total_residents: Dict[str, int] = {"lunch": 0, "dinner": 0}
        diet_names_global: Dict[str, str] = {}
        for dep_id, dep_name in departments:
            day = self._extract_day(tenant_id, year, week, dep_id, iso_date)
            meals_payload: Dict[str, Any] = {}
            for meal in ("lunch", "dinner"):
                residents_total = 0
                special_counts: Dict[str, int] = {}
                diet_names_local: Dict[str, str] = {}
                if day is not None:
                    try:
                        residents_total = int((day.get("residents") or {}).get(meal, 0) or 0)
                    except Exception:
                        residents_total = 0
                    # Include menu texts per meal from Weekview enrichment
                    try:
                        mt = day.get("menu_texts") or {}
                        mtm = mt.get(meal, {}) if isinstance(mt, dict) else {}
                        alt1_text = mtm.get("alt1")
                        alt2_text = mtm.get("alt2")
                        dessert_text = mtm.get("dessert") if meal == "lunch" else None
                    except Exception:
                        alt1_text = None
                        alt2_text = None
                        dessert_text = None
                    diets_arr = ((day.get("diets") or {}).get(meal)) or []
                    for it in diets_arr:
                        try:
                            if bool(it.get("marked")):
                                dtid = str(it.get("diet_type_id"))
                                cnt = int(it.get("resident_count") or 0)
                                if cnt > 0:
                                    special_counts[dtid] = special_counts.get(dtid, 0) + cnt
                                    name = str(it.get("diet_name") or dtid)
                                    diet_names_local[dtid] = name
                                    diet_names_global.setdefault(dtid, name)
                        except Exception:
                            continue
                specials_arr = [
                    {"diet_type_id": dtid, "diet_name": diet_names_local.get(dtid, dtid), "count": cnt}
                    for dtid, cnt in special_counts.items()
                    if cnt > 0
                ]
                try:
                    specials_arr.sort(key=lambda x: (-int(x.get("count", 0) or 0), str(x.get("diet_name") or "")))
                except Exception:
                    pass
                total_special = sum(int(x.get("count") or 0) for x in specials_arr)
                normal = residents_total - total_special
                if normal < 0:
                    normal = 0
                # Alt2 choice indicator: for lunch, derive from day flag; dinner optional/None in Phase 1
                alt_choice = None
                try:
                    if meal == "lunch":
                        alt_choice = "Alt2" if bool(day.get("alt2_lunch")) else ("Alt1" if alt1_text else None)
                    else:
                        # If dinner alt2 text exists, prefer Alt2; otherwise Alt1 when present
                        alt_choice = "Alt2" if alt2_text else ("Alt1" if alt1_text else None)
                except Exception:
                    alt_choice = None
                meals_payload[meal] = {
                    "residents_total": residents_total,
                    "special_diets": specials_arr,
                    "normal_diet_count": normal,
                    "alt1": alt1_text,
                    "alt2": alt2_text,
                    "dessert": dessert_text,
                    "alt_choice": alt_choice,
                }
                total_residents[meal] += residents_total
                for dtid, cnt in special_counts.items():
                    total_special_acc[meal][dtid] = total_special_acc[meal].get(dtid, 0) + cnt
            dep_out.append({"department_id": dep_id, "department_name": dep_name, "meals": meals_payload})
        totals_obj: Dict[str, Any] = {}
        for meal in ("lunch", "dinner"):
            specials_arr = [
                {"diet_type_id": dtid, "diet_name": diet_names_global.get(dtid, dtid), "count": cnt}
                for dtid, cnt in total_special_acc[meal].items()
                if cnt > 0
            ]
            try:
                specials_arr.sort(key=lambda x: (-int(x.get("count", 0) or 0), str(x.get("diet_name") or "")))
            except Exception:
                pass
            total_special = sum(int(x.get("count") or 0) for x in specials_arr)
            normal = total_residents[meal] - total_special
            if normal < 0:
                normal = 0
            totals_obj[meal] = {
                "residents_total": total_residents[meal],
                "special_diets": specials_arr,
                "normal_diet_count": normal,
            }
        return {"departments": dep_out, "totals": totals_obj}

    def compute_week(
        self,
        tenant_id: int | str,
        site_id: str,
        year: int,
        week: int,
        departments: Iterable[Tuple[str, str]],
    ) -> Dict[str, Any]:
        dept_days: Dict[str, List[Dict[str, Any]]] = {}
        for dep_id, _dep_name in departments:
            payload, _etag = self._weekview.fetch_weekview(tenant_id, year, week, dep_id)
            try:
                summaries = payload.get("department_summaries") or []
                days = (summaries[0].get("days") if summaries else []) or []
            except Exception:
                days = []
            dept_days[dep_id] = days
        weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        days_out: List[Dict[str, Any]] = []
        weekly_residents: Dict[str, int] = {"lunch": 0, "dinner": 0}
        weekly_special_acc: Dict[str, Dict[str, int]] = {"lunch": {}, "dinner": {}}
        diet_names_global: Dict[str, str] = {}
        for dow in range(1, 8):
            try:
                iso_date = _date.fromisocalendar(year, week, dow).isoformat()
            except Exception:
                iso_date = ""
            meals_out: Dict[str, Any] = {}
            day_residents: Dict[str, int] = {"lunch": 0, "dinner": 0}
            day_special_acc: Dict[str, Dict[str, int]] = {"lunch": {}, "dinner": {}}
            diet_names_day: Dict[str, str] = {}
            for dep_id, _dep_name in departments:
                day_obj = self._find_day(dept_days.get(dep_id, []), iso_date)
                if not day_obj:
                    continue
                for meal in ("lunch", "dinner"):
                    try:
                        day_residents[meal] += int((day_obj.get("residents") or {}).get(meal, 0) or 0)
                    except Exception:
                        pass
                    diets_arr = ((day_obj.get("diets") or {}).get(meal)) or []
                    for it in diets_arr:
                        try:
                            if bool(it.get("marked")):
                                dtid = str(it.get("diet_type_id"))
                                cnt = int(it.get("resident_count") or 0)
                                if cnt > 0:
                                    day_special_acc[meal][dtid] = day_special_acc[meal].get(dtid, 0) + cnt
                                    name = str(it.get("diet_name") or dtid)
                                    diet_names_day.setdefault(dtid, name)
                                    diet_names_global.setdefault(dtid, name)
                        except Exception:
                            continue
            for meal in ("lunch", "dinner"):
                specials_arr = [
                    {"diet_type_id": dtid, "diet_name": diet_names_day.get(dtid, dtid), "count": cnt}
                    for dtid, cnt in day_special_acc[meal].items()
                    if cnt > 0
                ]
                try:
                    specials_arr.sort(key=lambda x: (-int(x.get("count", 0) or 0), str(x.get("diet_name") or "")))
                except Exception:
                    pass
                total_special = sum(int(x.get("count") or 0) for x in specials_arr)
                normal = day_residents[meal] - total_special
                if normal < 0:
                    normal = 0
                meals_out[meal] = {
                    "residents_total": day_residents[meal],
                    "special_diets": specials_arr,
                    "normal_diet_count": normal,
                }
                weekly_residents[meal] += day_residents[meal]
                for dtid, cnt in day_special_acc[meal].items():
                    weekly_special_acc[meal][dtid] = weekly_special_acc[meal].get(dtid, 0) + cnt
            days_out.append(
                {
                    "day_of_week": dow,
                    "date": iso_date,
                    "weekday_name": weekday_names[dow - 1],
                    "meals": meals_out,
                }
            )
        weekly_totals: Dict[str, Any] = {}
        for meal in ("lunch", "dinner"):
            specials_arr = [
                {"diet_type_id": dtid, "diet_name": diet_names_global.get(dtid, dtid), "count": cnt}
                for dtid, cnt in weekly_special_acc[meal].items()
                if cnt > 0
            ]
            try:
                specials_arr.sort(key=lambda x: (-int(x.get("count", 0) or 0), str(x.get("diet_name") or "")))
            except Exception:
                pass
            total_special = sum(int(x.get("count") or 0) for x in specials_arr)
            normal = weekly_residents[meal] - total_special
            if normal < 0:
                normal = 0
            weekly_totals[meal] = {
                "residents_total": weekly_residents[meal],
                "special_diets": specials_arr,
                "normal_diet_count": normal,
            }
        return {"days": days_out, "weekly_totals": weekly_totals}

    def _extract_day(self, tenant_id: int | str, year: int, week: int, dep_id: str, iso_date: str) -> Dict[str, Any] | None:
        payload, _etag = self._weekview.fetch_weekview(tenant_id, year, week, dep_id)
        try:
            summaries = payload.get("department_summaries") or []
            day_list = (summaries[0].get("days") if summaries else []) or []
        except Exception:
            return None
        return self._find_day(day_list, iso_date)

    @staticmethod
    def _find_day(days: List[Dict[str, Any]], iso_date: str) -> Dict[str, Any] | None:
        for d in days:
            if d.get("date") == iso_date:
                return d
        return None
