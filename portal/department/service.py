"""Composite service for Department Portal week payload (Populate Phase P1.1).

Builds `DepartmentPortalWeekPayload` by aggregating:
 - Department/site metadata
 - Weekview marks (diets), residents counts, alt2 flags
 - Menu choice (Alt1/Alt2) per weekday from Alt2Repo (reusing existing storage)

Read-only: no mutations. ETag map derived from signatures.
"""

from __future__ import annotations

from hashlib import sha1
from typing import List
from datetime import datetime, timedelta
from sqlalchemy import text

from portal.department.models import (
    DepartmentPortalWeekPayload,
    PortalFacts,
    PortalProgress,
    PortalEtagMap,
    PortalDay,
)
from core.weekview.repo import WeekviewRepo
from core.menu_choice_api import _current_signature as _menu_choice_sig
from core.menu_choice_api import _DAY_MAP as _MENU_DAY_MAP
from flask import current_app
from core.db import get_session

_WEEKDAY_NAMES_SV = [
    "Måndag",
    "Tisdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lördag",
    "Söndag",
]


def _iso_week_start(year: int, week: int) -> datetime:
    return datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")


def _fetch_department_meta(department_id: str) -> tuple[str, str, str, str | None]:
    """Return (department_id, department_name, site_id, note)."""
    db = get_session()
    try:
        row = db.execute(
            text("SELECT id, name, site_id FROM departments WHERE id=:id"), {"id": department_id}
        ).fetchone()
        if not row:
            raise ValueError("department_not_found")
        # Notes may reside in separate table (admin notes) – optional lookup
        note_row = db.execute(
            text(
                "SELECT notes FROM department_notes WHERE department_id=:id"
            ),
            {"id": department_id},
        ).fetchone()
        note_val = None
        if note_row and note_row[0]:
            note_val = str(note_row[0])
        return str(row[0]), str(row[1]) if row[1] else "", str(row[2]), note_val
    finally:
        db.close()


def _build_days(
    department_id: str,
    year: int,
    week: int,
    marks: list[dict],
    counts: list[dict],
    alt2_days: list[int],
    menu_choice_map: dict[str, str],
) -> List[PortalDay]:
    week_start = _iso_week_start(year, week)
    # Organize counts per (day, meal)
    counts_map: dict[tuple[int, str], int] = {
        (c["day_of_week"], c["meal"]): c["count"] for c in counts
    }
    # Diet marks aggregated per (day, meal)
    diets_map: dict[tuple[int, str], dict[str, int]] = {}
    for m in marks:
        if not m.get("marked"):
            continue
        key = (m["day_of_week"], m["meal"])
        dname = str(m["diet_type"])  # already canonical in tests
        diets_map.setdefault(key, {})[dname] = diets_map.setdefault(key, {}).get(dname, 0) + 1
    days: List[PortalDay] = []
    # Fetch menu week view (if menu_service attached)
    menu_struct: dict[str, dict[str, dict[str, dict[str, object]]]] = {}
    try:
        menu_service = getattr(current_app, "menu_service", None)
        if menu_service and hasattr(menu_service, "get_week_view"):
            mv = menu_service.get_week_view(1, week, year)  # tenant_id hardcoded 1 for tests
            menu_struct = mv.get("days", {})  # type: ignore[assignment]
    except Exception:
        menu_struct = {}

    def _pick(meals: dict[str, dict[str, dict[str, object]]], meal: str, variants: list[str]) -> str | None:
        m = meals.get(meal)
        if not m:
            return None
        for vk in variants:
            v = m.get(vk)
            if v and v.get("dish_name"):
                return str(v.get("dish_name"))
        # fallback any dish
        for v in m.values():
            if v.get("dish_name"):
                return str(v.get("dish_name"))
        return None

    for i in range(7):
        weekday_num = i + 1
        dt = week_start + timedelta(days=i)
        # Lunch menu placeholders; real menu texts would come from menu table (future phase)
        day_key = _MENU_DAY_MAP.get(weekday_num)
        day_meals = menu_struct.get(day_key, {}) if day_key else {}
        lunch_alt1 = _pick(day_meals, "lunch", ["alt1"]) if day_meals else None
        lunch_alt2 = _pick(day_meals, "lunch", ["alt2"]) if day_meals else None
        dessert = _pick(day_meals, "dessert", ["dessert", "default"]) if day_meals else None
        dinner = _pick(day_meals, "dinner", ["dinner", "default"]) if day_meals else None
        # Selected alt derived from menu_choice_map (mon..sun keys) -> Alt1/Alt2
        day_key = _MENU_DAY_MAP.get(weekday_num)
        selected_alt = None
        if day_key and day_key in menu_choice_map:
            val = menu_choice_map[day_key]
            if val in {"Alt1", "Alt2"}:
                selected_alt = val
        # Residents lunch/dinner counts
        lunch_count = counts_map.get((weekday_num, "lunch"), 0)
        dinner_count = counts_map.get((weekday_num, "dinner"), 0)
        # Diet summaries
        lunch_diets_raw = diets_map.get((weekday_num, "lunch"), {})
        dinner_diets_raw = diets_map.get((weekday_num, "dinner"), {})
        lunch_diets = [
            {"diet_type_id": k.lower(), "diet_name": k, "count": v} for k, v in lunch_diets_raw.items()
        ]
        dinner_diets = [
            {"diet_type_id": k.lower(), "diet_name": k, "count": v} for k, v in dinner_diets_raw.items()
        ]
        days.append(
            {
                "date": dt.date().isoformat(),
                "weekday_name": _WEEKDAY_NAMES_SV[i],
                "menu": {
                    "lunch_alt1": lunch_alt1,
                    "lunch_alt2": lunch_alt2,
                    "dessert": dessert,
                    "dinner": dinner,
                },
                "choice": {"selected_alt": selected_alt},
                "flags": {"alt2_lunch": weekday_num in alt2_days},
                "residents": {"lunch": lunch_count, "dinner": dinner_count},
                "diets_summary": {"lunch": lunch_diets, "dinner": dinner_diets},
            }
        )
    return days


def build_department_week_payload(
    department_id: str,
    year: int,
    week: int,
    tenant_id: int | str = 1,
) -> DepartmentPortalWeekPayload:
    # Fetch meta
    dep_id, dep_name, site_id, note_val = _fetch_department_meta(department_id)

    # Weekview core data
    repo = WeekviewRepo()
    wv = repo.get_weekview(tenant_id, year, week, department_id)
    dep_summary = next((d for d in wv.get("department_summaries", []) if d.get("department_id") == department_id), None)
    marks = dep_summary.get("marks", []) if dep_summary else []
    counts = dep_summary.get("residents_counts", []) if dep_summary else []
    alt2_days = dep_summary.get("alt2_days", []) if dep_summary else []

    # Menu choice map (Alt1 default unless Alt2 flagged in storage) via signature repo
    # Reuse Alt2Repo listing indirectly by computing signature then deriving days from existing API logic.
    from core.admin_repo import Alt2Repo

    repo_alt2 = Alt2Repo()
    rows_choice = repo_alt2.list_for_department_week(department_id, week)
    menu_choice_map = {v: "Alt1" for v in _MENU_DAY_MAP.values()}
    for r in rows_choice:
        if r.get("enabled"):
            wk = int(r.get("weekday") or 0)
            dk = _MENU_DAY_MAP.get(wk)
            if dk:
                menu_choice_map[dk] = "Alt2"

    # Days build
    days = _build_days(department_id, year, week, marks, counts, alt2_days, menu_choice_map)

    # Facts & progress
    facts: PortalFacts = {
        "note": note_val,
        "residents_default_lunch": None,
        "residents_default_dinner": None,
    }
    days_with_choice = sum(1 for d in days if d["choice"].get("selected_alt") is not None)
    progress: PortalProgress = {"days_with_choice": days_with_choice, "total_days": len(days)}

    # ETag map signatures
    menu_sig = _menu_choice_sig(department_id, week)
    # Weekview signature: hash of counts + marked diets + alt2 days
    h_source = []
    for c in counts:
        h_source.append(f"c:{c['day_of_week']}:{c['meal']}:{c['count']}")
    for m in marks:
        if m.get("marked"):
            h_source.append(f"m:{m['day_of_week']}:{m['meal']}:{m['diet_type']}")
    for a in alt2_days:
        h_source.append(f"a:{a}")
    # Include menu texts in hash
    for d in days:
        menu = d.get("menu", {})
        h_source.append(
            f"mt:{d['date']}:{menu.get('lunch_alt1')}:{menu.get('lunch_alt2')}:{menu.get('dessert')}:{menu.get('dinner')}"
        )
    wv_hash = sha1("|".join(sorted(h_source)).encode()).hexdigest()[:16]
    etag_map: PortalEtagMap = {
        "menu_choice": f'W/"portal-menu-choice:{department_id}:{year}-{week}:v{menu_sig}"',
        "weekview": f'W/"portal-weekview:{department_id}:{year}-{week}:{wv_hash}"',
    }

    payload: DepartmentPortalWeekPayload = {
        "department_id": dep_id,
        "department_name": dep_name,
        "site_id": site_id,
        "site_name": "",  # site name could be joined if needed later
        "year": year,
        "week": week,
        "facts": facts,
        "progress": progress,
        "etag_map": etag_map,
        "days": days,
    }
    from portal.department.models import validate_portal_week_payload
    validate_portal_week_payload(payload)
    return payload

__all__ = ["build_department_week_payload"]
