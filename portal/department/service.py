"""Composite service for Department Portal week payload (Populate Phase P1.1).

Builds `DepartmentPortalWeekPayload` by aggregating:
 - Department/site metadata
 - Weekview marks (diets), residents counts, alt2 flags
 - Explicit department menu choice (Alt1/Alt2) per weekday from dedicated MenuChoiceRepo; Weekview Alt2 remains separate operational state
 - Canonical published Builder menu text via publication/projection

Read-only: no mutations. ETag map derived from signatures.
"""

from __future__ import annotations

from hashlib import sha1
from typing import List
from datetime import datetime, timedelta
from sqlalchemy import text

from core.commun_builder_publication import CommunBuilderPublicationService
from core.commun_builder_projection import get_shadow_projection_reader
from core.db import get_session
from portal.department.auth import DepartmentPortalScope
from portal.department.menu_choice_repo import MenuChoiceRepo
from portal.department.models import (
    DepartmentPortalWeekPayload,
    PortalFacts,
    PortalProgress,
    PortalEtagMap,
    PortalDay,
)
from core.weekview.repo import WeekviewRepo

_WEEKDAY_NAMES_SV = [
    "Måndag",
    "Tisdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lördag",
    "Söndag",
]

_DAY_NAME_TO_CODE = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}

_MENU_DAY_MAP = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


def _iso_week_start(year: int, week: int) -> datetime:
    return datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")


def _fetch_department_meta(department_id: str) -> tuple[str, str, str | None]:
    """Return (department_id, department_name, note)."""
    db = get_session()
    try:
        row = db.execute(
            text("SELECT id, name, COALESCE(notes, '') FROM departments WHERE id=:id"),
            {"id": department_id},
        ).fetchone()
        if not row:
            raise ValueError("department_not_found")
        note_val = str(row[2]) if row[2] is not None else ""
        return str(row[0]), str(row[1]) if row[1] else "", note_val
    finally:
        db.close()


def _load_canonical_menu_struct(*, tenant_id: int | str, site_id: str, year: int, week: int) -> dict[str, dict[str, dict[str, dict[str, object]]]]:
    publication = CommunBuilderPublicationService().get_publication_for_week(
        tenant_id=int(tenant_id),
        site_id=site_id,
        year=year,
        week=week,
    )
    if publication is None:
        return {}

    outcome = get_shadow_projection_reader().get_projection_for_pinned_menu(
        tenant_id=int(tenant_id),
        site_id=site_id,
        year=year,
        week=week,
        builder_menu_id=str(publication.builder_menu_id),
        builder_menu_version=int(publication.builder_menu_version),
    )
    projection = outcome.projection
    if outcome.status == "no_publication":
        return {}
    if outcome.status != "ok" or projection is None:
        raise RuntimeError(f"publication_projection_broken:{outcome.error or outcome.status}")
        return {}

    menu_struct: dict[str, dict[str, dict[str, dict[str, object]]]] = {}
    for row in projection.rows:
        menu_day = _DAY_NAME_TO_CODE.get(str(row.day).strip().lower(), str(row.day).strip().lower())
        menu_struct.setdefault(menu_day, {}).setdefault(row.meal, {})[row.variant_type] = {"dish_name": row.text}
    return menu_struct


def _build_days(
    department_id: str,
    year: int,
    week: int,
    menu_struct: dict[str, dict[str, dict[str, dict[str, object]]]],
    marks: list[dict],
    counts: list[dict],
    alt2_days: list[int],
    menu_choice_map: dict[str, str | None],
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
        dessert = _pick(day_meals, "lunch", ["dessert", "default"]) if day_meals else None
        dinner = _pick(day_meals, "dinner", ["alt1", "main", "dinner", "default"]) if day_meals else None
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
        has_diets = bool(lunch_diets) or bool(dinner_diets)
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
                "has_diets": has_diets,
            }
        )
    return days


def build_department_week_payload(
    scope: DepartmentPortalScope,
    year: int,
    week: int,
) -> DepartmentPortalWeekPayload:
    department_id = scope.department_id
    tenant_id = scope.tenant_id
    site_id = scope.site_id
    # Fetch meta
    dep_id, dep_name, note_val = _fetch_department_meta(department_id)
    # Resolve site name for header display (best-effort)
    site_name_val = ""
    try:
        dbn = get_session()
        try:
            row_site = dbn.execute(text("SELECT name FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
            if row_site and row_site[0]:
                site_name_val = str(row_site[0])
        finally:
            dbn.close()
    except Exception:
        site_name_val = ""

    # Weekview core data
    repo = WeekviewRepo()
    wv = repo.get_weekview(tenant_id, year, week, department_id)
    dep_summary = next((d for d in wv.get("department_summaries", []) if d.get("department_id") == department_id), None)
    marks = dep_summary.get("marks", []) if dep_summary else []
    counts = dep_summary.get("residents_counts", []) if dep_summary else []
    alt2_days = dep_summary.get("alt2_days", []) if dep_summary else []

    menu_struct = _load_canonical_menu_struct(tenant_id=tenant_id, site_id=site_id, year=year, week=week)

    choice_repo = MenuChoiceRepo()
    menu_choice_map = choice_repo.derive_map(
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
    )

    # Days build
    days = _build_days(department_id, year, week, menu_struct, marks, counts, alt2_days, menu_choice_map)

    # Facts & progress
    facts: PortalFacts = {
        "note": note_val,
        "residents_default_lunch": None,
        "residents_default_dinner": None,
    }
    days_with_choice = sum(1 for d in days if d["choice"].get("selected_alt") is not None)
    progress: PortalProgress = {"days_with_choice": days_with_choice, "total_days": len(days)}

    # Simple summary counts for registered lunch/dinner days (count > 0 considered registered)
    registered_lunch_days = sum(1 for d in days if (d.get("residents", {}).get("lunch") or 0) > 0)
    registered_dinner_days = sum(1 for d in days if (d.get("residents", {}).get("dinner") or 0) > 0)
    diet_days_count = sum(1 for d in days if d.get("has_diets"))

    # ETag map signatures
    menu_sig = choice_repo.get_signature(
        tenant_id=tenant_id,
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
    )
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
        "menu_choice": menu_sig,
        "weekview": f'W/"portal-weekview:{department_id}:{year}-{week}:{wv_hash}"',
    }

    payload: DepartmentPortalWeekPayload = {
        "department_id": dep_id,
        "department_name": dep_name,
        "site_id": site_id,
        "site_name": site_name_val,
        "year": year,
        "week": week,
        "facts": facts,
        "progress": progress,
        "etag_map": etag_map,
        "days": days,
        "summary": {"registered_lunch_days": registered_lunch_days, "registered_dinner_days": registered_dinner_days, "diet_days_count": diet_days_count},
    }
    from portal.department.models import validate_portal_week_payload
    validate_portal_week_payload(payload)
    return payload

__all__ = ["build_department_week_payload"]
