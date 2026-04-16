from __future__ import annotations

from datetime import date
from typing import Any, Iterable
import unicodedata

from sqlalchemy import text

from ...db import get_session
from ...planera_service import PlaneraService
from ..domain import Deviation, PlanRequest, UnitInput


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_meal_key(value: object) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    ascii_only = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return ascii_only


def _resolve_meal_data(meals: dict[str, Any], meal_key: str) -> dict[str, Any]:
    lookup: dict[str, dict[str, Any]] = {}
    for key, value in meals.items():
        if isinstance(value, dict):
            lookup[_normalize_meal_key(key)] = value

    requested = _normalize_meal_key(meal_key)
    candidates = [requested]
    if requested in {"kvall", "kvallsmat", "evening"}:
        candidates.append("dinner")
    elif requested == "dinner":
        candidates.extend(["kvallsmat", "kvall"])

    for candidate in candidates:
        resolved = lookup.get(candidate)
        if isinstance(resolved, dict):
            return resolved
    return {}


def _resolve_departments_for_site(site_id: str) -> list[tuple[str, str]]:
    db = get_session()
    try:
        rows = db.execute(
            text("SELECT id, name FROM departments WHERE site_id=:site_id ORDER BY name, id"),
            {"site_id": site_id},
        ).fetchall()
    finally:
        db.close()

    out: list[tuple[str, str]] = []
    for row in rows:
        dep_id = str(row[0] or "").strip()
        dep_name = str(row[1] or "")
        if dep_id:
            out.append((dep_id, dep_name))
    return out


def _build_request_from_planera_day_payload(
    day_payload: dict[str, Any],
    *,
    site_id: str,
    iso_date: str,
    meal_key: str,
) -> PlanRequest:
    units: list[UnitInput] = []
    deviations: list[Deviation] = []
    menu_option_by_unit: dict[str, str] = {}

    departments = day_payload.get("departments")
    if not isinstance(departments, list):
        departments = []

    baseline_total = 0

    for dep in departments:
        if not isinstance(dep, dict):
            continue

        unit_id = str(dep.get("department_id") or "").strip()
        if not unit_id:
            continue

        meals = dep.get("meals") if isinstance(dep.get("meals"), dict) else {}
        meal_data = _resolve_meal_data(meals, meal_key)

        residents_total = _to_int(meal_data.get("residents_total"), default=0)
        if residents_total < 0:
            residents_total = 0

        units.append(UnitInput(unit_id=unit_id, baseline_total=residents_total))
        baseline_total += residents_total

        alt_choice = meal_data.get("alt_choice")
        if isinstance(alt_choice, str) and alt_choice.strip():
            menu_option_by_unit[unit_id] = alt_choice.strip()

        # Source of truth is effective special_diets for this day+meal.
        # We intentionally do not map raw weekview marks directly as deviations here.
        special_diets = meal_data.get("special_diets")
        if not isinstance(special_diets, list):
            special_diets = []

        for item in special_diets:
            if not isinstance(item, dict):
                continue
            quantity = _to_int(item.get("count"), default=0)
            if quantity <= 0:
                continue

            category_key = str(item.get("diet_type_id") or item.get("diet_name") or "").strip()
            if not category_key:
                continue

            # Temporary adapter-level fallback label:
            # - "specialkost" here is NOT authoritative form semantics.
            # - Exact form truth requires upstream source support in current Planera/Weekview data.
            deviations.append(
                Deviation(
                    form="specialkost",
                    category_keys=[category_key],
                    quantity=quantity,
                    unit_id=unit_id,
                )
            )

    context: dict[str, object] = {
        "source": "current_planera_day",
        "site_id": site_id,
        "date": iso_date,
        "meal_key": meal_key,
    }
    try:
        d = date.fromisoformat(iso_date)
        year, week, day_of_week = d.isocalendar()
        context["year"] = year
        context["week"] = week
        context["day_of_week"] = day_of_week
    except ValueError:
        pass

    if menu_option_by_unit:
        context["menu_option_by_unit"] = menu_option_by_unit

    return PlanRequest(
        baseline=baseline_total,
        units=units,
        deviations=deviations,
        context=context,
    )


def build_plan_request_from_weekview_day(
    tenant_id: int | str,
    site_id: str,
    iso_date: str,
    meal: str,
    *,
    planera_service: PlaneraService | None = None,
    departments: Iterable[tuple[str, str]] | None = None,
) -> PlanRequest:
    meal_key = str(meal or "").strip().lower()
    if not meal_key:
        raise ValueError("meal must be a non-empty string")

    svc = planera_service or PlaneraService()
    dep_list = list(departments) if departments is not None else _resolve_departments_for_site(site_id)

    day_payload = svc.compute_day(
        tenant_id=tenant_id,
        site_id=site_id,
        iso_date=iso_date,
        departments=dep_list,
    )

    if not isinstance(day_payload, dict):
        day_payload = {}

    return _build_request_from_planera_day_payload(
        day_payload,
        site_id=site_id,
        iso_date=iso_date,
        meal_key=meal_key,
    )
