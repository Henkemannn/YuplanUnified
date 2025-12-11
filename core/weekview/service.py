from __future__ import annotations

import re
from datetime import date
from typing import Sequence, Any
from flask import current_app
from ..admin_repo import DietDefaultsRepo
from sqlalchemy import text
from ..residents_weekly_repo import ResidentsWeeklyRepo
from ..residents_schedule_repo import ResidentsScheduleRepo
from ..db import get_session
from .repo import WeekviewRepo


class WeekviewService:
    def __init__(self, repo: WeekviewRepo | None = None) -> None:
        self.repo = repo or WeekviewRepo()

    def resolve(self, site: str, department_id: str, date: str) -> dict:
        # Phase A: minimal placeholder context
        return {"site": site, "department_id": department_id, "date": date}

    def build_etag(self, tenant_id: int | str, department_id: str, year: int, week: int, version: int) -> str:
        # Weak ETag format per spec
        return f'W/"weekview:dept:{department_id}:year:{year}:week:{week}:v{version}"'

    def fetch_weekview(self, tenant_id: int | str, year: int, week: int, department_id: str | None) -> tuple[dict, str]:
        dep = department_id or "__none__"
        version = 0 if not department_id else self.repo.get_version(tenant_id, year, week, department_id)
        payload = self.repo.get_weekview(tenant_id, year, week, department_id)
        # Enrich with Phase 1 days[] structure for UI (backwards compatible)
        try:
            self._enrich_days(payload, tenant_id, year, week)
        except Exception:
            # Non-fatal: keep existing payload if enrichment fails
            pass
        etag = self.build_etag(tenant_id, dep, year, week, version)
        return payload, etag


class EtagMismatchError(Exception):
    pass


class WeekviewService(WeekviewService):  # type: ignore[misc]
    _ETAG_RE = re.compile(r'^W/"weekview:dept:(?P<dep>[0-9a-fA-F\-]+):year:(?P<yy>\d{4}):week:(?P<ww>\d{1,2}):v(?P<v>\d+)"$')

    def toggle_marks(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        if_match: str,
        ops: Sequence[dict],
    ) -> str:
        m = self._ETAG_RE.match(if_match or "")
        if not m:
            raise EtagMismatchError("invalid_if_match")
        # Validate target tuple in ETag matches request
        dep = m.group("dep")
        yy = int(m.group("yy"))
        ww = int(m.group("ww"))
        v = int(m.group("v"))
        if dep != department_id or yy != year or ww != week:
            raise EtagMismatchError("etag_mismatch")
        current = self.repo.get_version(tenant_id, year, week, department_id)
        if current != v:
            raise EtagMismatchError("etag_mismatch")
        new_version = self.repo.apply_operations(tenant_id, year, week, department_id, ops)
        return self.build_etag(tenant_id, department_id, year, week, new_version)

    def fetch_weekview_conditional(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str | None,
        if_none_match: str | None,
    ) -> tuple[bool, dict | None, str]:
        """
        Returns (not_modified, payload, etag). If not_modified is True, payload will be None.
        """
        dep = department_id or "__none__"
        version = 0 if not department_id else self.repo.get_version(tenant_id, year, week, department_id)
        etag = self.build_etag(tenant_id, dep, year, week, version)
        if if_none_match and if_none_match == etag:
            return True, None, etag
        payload = self.repo.get_weekview(tenant_id, year, week, department_id)
        try:
            self._enrich_days(payload, tenant_id, year, week)
        except Exception:
            pass
        return False, payload, etag

    def update_residents_counts(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        if_match: str,
        items: Sequence[dict],
    ) -> str:
        m = self._ETAG_RE.match(if_match or "")
        if not m:
            raise EtagMismatchError("invalid_if_match")
        dep = m.group("dep")
        yy = int(m.group("yy"))
        ww = int(m.group("ww"))
        v = int(m.group("v"))
        if dep != department_id or yy != year or ww != week:
            raise EtagMismatchError("etag_mismatch")
        current = self.repo.get_version(tenant_id, year, week, department_id)
        if current != v:
            raise EtagMismatchError("etag_mismatch")
        new_v = self.repo.set_residents_counts(tenant_id, year, week, department_id, items)
        return self.build_etag(tenant_id, department_id, year, week, new_v)

    def update_alt2_flags(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        if_match: str,
        days: Sequence[int],
    ) -> str:
        m = self._ETAG_RE.match(if_match or "")
        if not m:
            raise EtagMismatchError("invalid_if_match")
        dep = m.group("dep")
        yy = int(m.group("yy"))
        ww = int(m.group("ww"))
        v = int(m.group("v"))
        if dep != department_id or yy != year or ww != week:
            raise EtagMismatchError("etag_mismatch")
        current = self.repo.get_version(tenant_id, year, week, department_id)
        if current != v:
            raise EtagMismatchError("etag_mismatch")
        new_v = self.repo.set_alt2_flags(tenant_id, year, week, department_id, days)
        return self.build_etag(tenant_id, department_id, year, week, new_v)

    # --- Residents helpers (v1) ---
    def get_effective_residents_for_week(self, department_id: str, year: int, week: int) -> dict:
        """Return effective residents for lunch/dinner for the given week.

        Uses weekly override from ResidentsWeeklyRepo; falls back to department.resident_count_fixed.
        """
        # Fetch fixed from departments
        fixed = 0
        db = get_session()
        try:
            row = db.execute(
                text("SELECT COALESCE(resident_count_fixed,0) FROM departments WHERE id=:id"),
                {"id": department_id},
            ).fetchone()
            fixed = int(row[0] or 0) if row else 0
        finally:
            db.close()
        # Weekly override
        ov = {}
        try:
            ov = ResidentsWeeklyRepo().get_for_week(department_id, year, week) or {}
        except Exception:
            ov = {}
        lunch = int((ov.get("residents_lunch") if ov else None) or fixed)
        dinner = int((ov.get("residents_dinner") if ov else None) or fixed)
        return {
            "lunch": lunch,
            "dinner": dinner,
            "has_override": bool(ov.get("residents_lunch") or ov.get("residents_dinner")),
        }

    def get_effective_residents_for_day(self, department_id: str, year: int, week: int, weekday: int) -> dict:
        """Precedence:
        1) Weekly per-day schedule in department_residents_schedule
        2) Forever per-day schedule
        3) Weekly override (legacy same-for-week)
        4) Fixed

        Returns {"lunch": int, "dinner": int, "source": "schedule_week"|"schedule_forever"|"weekly_override"|"fixed"}.
        """
        # 1/2: per-day schedules
        try:
            repo = ResidentsScheduleRepo()
            week_items = { (int(it["weekday"]), str(it["meal"])): int(it["count"]) for it in repo.get_week(department_id, week) }
            forever_items = { (int(it["weekday"]), str(it["meal"])): int(it["count"]) for it in repo.get_forever(department_id) }
        except Exception:
            week_items, forever_items = {}, {}
        if (weekday, "lunch") in week_items or (weekday, "dinner") in week_items:
            return {
                "lunch": int(week_items.get((weekday, "lunch"), 0)),
                "dinner": int(week_items.get((weekday, "dinner"), 0)),
                "source": "schedule_week",
            }
        if (weekday, "lunch") in forever_items or (weekday, "dinner") in forever_items:
            return {
                "lunch": int(forever_items.get((weekday, "lunch"), 0)),
                "dinner": int(forever_items.get((weekday, "dinner"), 0)),
                "source": "schedule_forever",
            }
        # 3/4: legacy weekly override or fixed
        wk = self.get_effective_residents_for_week(department_id, year, week)
        src = "weekly_override" if wk.get("has_override") else "fixed"
        return {"lunch": int(wk["lunch"]), "dinner": int(wk["dinner"]), "source": src}

    # --- Internal helpers ---
    def _enrich_days(self, payload: dict, tenant_id: int | str, year: int, week: int) -> None:
        """Populate department_summaries[*].days with Phase 1 fields.

        Keeps existing keys (marks, residents_counts, alt2_days) for backward compatibility.
        Adds per-day objects:
          { day_of_week, date, weekday_name, menu_texts, alt2_lunch, residents }
        """
        try:
            summaries: list[dict[str, Any]] = payload.get("department_summaries", [])  # type: ignore[assignment]
        except Exception:
            return
        if not summaries:
            return
        # Resolve menu texts for the week (optional service)
        menu_days: dict[str, Any] = {}
        try:
            svc = getattr(current_app, "menu_service", None)
            if svc is not None:
                mv = svc.get_week_view(int(tenant_id), week, year)
                menu_days = dict(mv.get("days", {}))
        except Exception:
            menu_days = {}

        # Helper maps
        day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        name_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for summary in summaries:
            # Build quick indexes from existing aggregates
            counts = summary.get("residents_counts", []) or []
            alt2_days = set(summary.get("alt2_days", []) or [])
            counts_idx: dict[tuple[int, str], int] = {}
            try:
                for r in counts:
                    k = (int(r.get("day_of_week")), str(r.get("meal")))
                    counts_idx[k] = int(r.get("count"))
            except Exception:
                counts_idx = {}

            # Resolve department id for diet defaults
            dept_id = str(summary.get("department_id") or "").strip()
            diet_defaults: dict[str, int] = {}
            try:
                if dept_id:
                    repo = DietDefaultsRepo()
                    items = repo.list_for_department(dept_id)
                    diet_defaults = {str(it["diet_type_id"]): int(it.get("default_count", 0)) for it in items}
            except Exception:
                diet_defaults = {}

            # Build mark index from raw marks list if present
            marks = summary.get("marks", []) or []
            marked_idx: set[tuple[int, str, str]] = set()
            try:
                for m in marks:
                    if bool(m.get("marked")):
                        marked_idx.add((int(m.get("day_of_week")), str(m.get("meal")), str(m.get("diet_type"))))
            except Exception:
                marked_idx = set()

            days_out: list[dict[str, Any]] = []
            for dow in range(1, 8):
                iso_date = None
                try:
                    iso_date = date.fromisocalendar(year, week, dow).isoformat()
                except Exception:
                    iso_date = None
                dkey = day_keys[dow - 1]
                # menu_texts lookup
                menu_for_day = menu_days.get(dkey, {}) if isinstance(menu_days, dict) else {}
                def _dish_name(meal: str, variant: str) -> str | None:
                    try:
                        v = menu_for_day.get(meal, {}).get(variant)
                        if v is None:
                            return None
                        return v.get("dish_name")
                    except Exception:
                        return None

                menu_texts = {}
                # lunch always relevant in Phase 1
                lunch_obj: dict[str, Any] = {}
                a1 = _dish_name("lunch", "alt1")
                a2 = _dish_name("lunch", "alt2")
                if a1 is not None:
                    lunch_obj["alt1"] = a1
                if a2 is not None:
                    lunch_obj["alt2"] = a2
                # Optional dessert if modeled
                dessert = _dish_name("lunch", "dessert")
                if dessert is not None:
                    lunch_obj["dessert"] = dessert
                if lunch_obj:
                    menu_texts["lunch"] = lunch_obj

                # dinner (kväll) optional in Phase 1
                dinner_obj: dict[str, Any] = {}
                d1 = _dish_name("dinner", "alt1")
                d2 = _dish_name("dinner", "alt2")
                if d1 is not None:
                    dinner_obj["alt1"] = d1
                if d2 is not None:
                    dinner_obj["alt2"] = d2
                if dinner_obj:
                    menu_texts["dinner"] = dinner_obj

                # Build diets list per meal using department defaults and marks
                def _build_diets(meal_name: str) -> list[dict[str, Any]]:
                    out: list[dict[str, Any]] = []
                    for dt_id, default_cnt in sorted(diet_defaults.items()):
                        out.append(
                            {
                                "diet_type_id": dt_id,
                                "diet_name": dt_id,  # TODO: map id->human name via diet types registry
                                "resident_count": int(default_cnt),
                                "marked": (dow, meal_name, dt_id) in marked_idx,
                            }
                        )
                    return out

                # Residents v1: use effective values per day from admin data
                eff = self.get_effective_residents_for_day(dept_id, year, week, dow)
                # Apply per-day overrides from residents_counts if present
                rl = int(counts_idx.get((dow, "lunch"), eff.get("lunch", 0)) or 0)
                rd = int(counts_idx.get((dow, "dinner"), eff.get("dinner", 0)) or 0)
                days_out.append(
                    {
                        "day_of_week": dow,
                        "date": iso_date,
                        "weekday_name": name_map[dow - 1],
                        "menu_texts": menu_texts,
                        "alt2_lunch": (dow in alt2_days),
                        "residents": {
                            "lunch": rl,
                            "dinner": rd,
                        },
                        "diets": {
                            "lunch": _build_diets("lunch"),
                            "dinner": _build_diets("dinner"),
                        },
                    }
                )
            summary["days"] = days_out
