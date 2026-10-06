from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Any, Iterable

from sqlalchemy import text

from .db import get_session
from .department_requirement_group_quantity_resolver import resolve_effective_quantity
from .department_requirement_group_service_overrides_repo import resolve_effective_quantity_in_session


_WEEKDAY_LABELS = {
    1: "Mån",
    2: "Tis",
    3: "Ons",
    4: "Tors",
    5: "Fre",
    6: "Lör",
    7: "Sön",
}


@dataclass(frozen=True, slots=True)
class DepartmentVariationSaveResult:
    resident_changes: bool
    need_changes: bool
    scope: str


def _selected_week_dates(year: int, week: int) -> list[_date]:
    return [_date.fromisocalendar(int(year), int(week), weekday) for weekday in range(1, 8)]


def _ensure_tables(db) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS department_residents_schedule (
                department_id TEXT NOT NULL,
                week INTEGER,
                weekday INTEGER NOT NULL,
                meal TEXT NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY(department_id, week, weekday, meal)
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS department_residents_weekly (
                id TEXT PRIMARY KEY,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                residents_lunch INTEGER NULL,
                residents_dinner INTEGER NULL,
                updated_at TEXT
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_dept_res_week
            ON department_residents_weekly(department_id, year, week)
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS department_requirement_group_weekday_overrides (
                group_id TEXT NOT NULL,
                weekday INTEGER NOT NULL,
                meal_key TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                PRIMARY KEY(group_id, weekday, meal_key)
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS department_requirement_group_service_overrides (
                group_id TEXT NOT NULL,
                service_date DATE NOT NULL,
                meal_key TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY(group_id, service_date, meal_key)
            )
            """
        )
    )


def _normalize_scope(value: object) -> str:
    scope = str(value or "week").strip().lower()
    if scope not in {"week", "forever"}:
        return "week"
    return scope


def _parse_int(value: object) -> int:
    return int(str(value).strip())


def build_requirement_group_variation_rows(group_id: str, *, year: int, week: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for weekday, service_date in enumerate(_selected_week_dates(year, week), start=1):
        rows.append(
            {
                "weekday": weekday,
                "weekday_label": _WEEKDAY_LABELS.get(weekday, str(weekday)),
                "lunch_value": resolve_effective_quantity(group_id, service_date, "lunch"),
                "dinner_value": resolve_effective_quantity(group_id, service_date, "dinner"),
            }
        )
    return rows


def build_requirement_group_variation_rows_in_session(db, group_id: str, *, year: int, week: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for weekday, service_date in enumerate(_selected_week_dates(year, week), start=1):
        rows.append(
            {
                "weekday": weekday,
                "weekday_label": _WEEKDAY_LABELS.get(weekday, str(weekday)),
                "lunch_value": resolve_effective_quantity_in_session(db, group_id, 0, True, service_date, "lunch"),
                "dinner_value": resolve_effective_quantity_in_session(db, group_id, 0, True, service_date, "dinner"),
            }
        )
    return rows


def _resident_rows_for_scope_in_session(db, *, department_id: str, year: int, week: int) -> dict[int, dict[str, int]]:
    week_rows = db.execute(
        text(
            """
            SELECT weekday, meal, count
            FROM department_residents_schedule
            WHERE department_id=:department_id AND week=:week
            """
        ),
        {"department_id": department_id, "week": int(week)},
    ).fetchall()
    week_map: dict[tuple[int, str], int] = {}
    for row in week_rows:
        try:
            week_map[(int(row[0]), str(row[1]))] = int(row[2] or 0)
        except Exception:
            continue
    forever_rows = db.execute(
        text(
            """
            SELECT weekday, meal, count
            FROM department_residents_schedule
            WHERE department_id=:department_id AND week IS NULL
            """
        ),
        {"department_id": department_id},
    ).fetchall()
    forever_map: dict[tuple[int, str], int] = {}
    for row in forever_rows:
        try:
            forever_map[(int(row[0]), str(row[1]))] = int(row[2] or 0)
        except Exception:
            continue

    row = db.execute(
        text("SELECT COALESCE(resident_count_fixed,0) FROM departments WHERE id=:department_id"),
        {"department_id": department_id},
    ).fetchone()
    fixed = int(row[0] or 0) if row else 0
    week_override = db.execute(
        text(
            """
            SELECT residents_lunch, residents_dinner
            FROM department_residents_weekly
            WHERE department_id=:department_id AND year=:year AND week=:week
            """
        ),
        {"department_id": department_id, "year": int(year), "week": int(week)},
    ).fetchone()
    lunch = int((week_override[0] if week_override else None) or fixed)
    dinner = int((week_override[1] if week_override else None) or fixed)
    out: dict[int, dict[str, int]] = {}
    for weekday in range(1, 8):
        if (weekday, "lunch") in week_map or (weekday, "dinner") in week_map:
            out[weekday] = {
                "lunch": int(week_map.get((weekday, "lunch"), 0)),
                "dinner": int(week_map.get((weekday, "dinner"), 0)),
            }
            continue
        if (weekday, "lunch") in forever_map or (weekday, "dinner") in forever_map:
            out[weekday] = {
                "lunch": int(forever_map.get((weekday, "lunch"), 0)),
                "dinner": int(forever_map.get((weekday, "dinner"), 0)),
            }
            continue
        out[weekday] = {"lunch": lunch, "dinner": dinner}
    return out


def _parse_resident_items(form: Any) -> list[dict[str, int | str]]:
    items: list[dict[str, int | str]] = []
    for weekday in range(1, 8):
        for meal in ("lunch", "dinner"):
            raw_value = form.get(f"day_{weekday}_{meal}")
            if raw_value is None:
                continue
            clean_value = str(raw_value).strip()
            if clean_value == "":
                continue
            count = _parse_int(clean_value)
            if count < 0:
                raise ValueError("quantity_negative")
            items.append({"weekday": weekday, "meal": meal, "count": count})
    return items


def _parse_need_cells(form: Any) -> dict[str, dict[tuple[int, str], str]]:
    grouped: dict[str, dict[tuple[int, str], str]] = {}
    for key, raw_value in form.items():
        if not str(key).startswith("need_day_"):
            continue
        suffix = str(key)[len("need_day_") :]
        try:
            group_id, weekday_raw, meal_key = suffix.rsplit("_", 2)
        except ValueError:
            continue
        if meal_key not in {"lunch", "dinner"}:
            continue
        try:
            weekday = int(weekday_raw)
        except Exception:
            continue
        if weekday < 1 or weekday > 7:
            continue
        grouped.setdefault(group_id, {})[(weekday, meal_key)] = str(raw_value)
    return grouped


def _apply_resident_changes(db, *, department_id: str, scope: str, year: int, week: int, resident_items: list[dict[str, int | str]]) -> None:
    if scope == "forever":
        db.execute(
            text("DELETE FROM department_residents_schedule WHERE department_id=:department_id AND week IS NULL"),
            {"department_id": department_id},
        )
        target_week = None
    else:
        db.execute(
            text("DELETE FROM department_residents_schedule WHERE department_id=:department_id AND week=:week"),
            {"department_id": department_id, "week": int(week)},
        )
        target_week = int(week)

    for item in resident_items:
        db.execute(
            text(
                """
                INSERT INTO department_residents_schedule(department_id, week, weekday, meal, count)
                VALUES(:department_id, :week, :weekday, :meal, :count)
                ON CONFLICT(department_id, week, weekday, meal)
                DO UPDATE SET count=excluded.count
                """
            ),
            {
                "department_id": department_id,
                "week": target_week,
                "weekday": int(item["weekday"]),
                "meal": str(item["meal"]),
                "count": int(item["count"]),
            },
        )


def _apply_need_changes(db, *, department_id: str, scope: str, year: int, week: int, need_cells: dict[str, dict[tuple[int, str], str]]) -> bool:
    if not need_cells:
        return False

    group_rows = db.execute(
        text(
            """
            SELECT id, default_quantity, is_active
            FROM department_requirement_groups
            WHERE department_id=:department_id
            ORDER BY id ASC
            """
        ),
        {"department_id": department_id},
    ).fetchall()
    group_index = {str(row[0]): (int(row[1] or 0), bool(row[2])) for row in group_rows}
    touched = False

    for group_id, cells in need_cells.items():
        if group_id not in group_index:
            raise ValueError("department_requirement_group_not_found")
        default_quantity, is_active = group_index[group_id]
        for weekday in range(1, 8):
            service_date = _date.fromisocalendar(int(year), int(week), weekday)
            for meal_key in ("lunch", "dinner"):
                raw_value = cells.get((weekday, meal_key))
                if raw_value is None:
                    continue
                clean_value = str(raw_value).strip()
                if clean_value == "":
                    if scope == "forever":
                        db.execute(
                            text(
                                """
                                DELETE FROM department_requirement_group_weekday_overrides
                                WHERE group_id=:group_id AND weekday=:weekday AND meal_key=:meal_key
                                """
                            ),
                            {"group_id": group_id, "weekday": weekday, "meal_key": meal_key},
                        )
                    else:
                        db.execute(
                            text(
                                """
                                DELETE FROM department_requirement_group_service_overrides
                                WHERE group_id=:group_id AND service_date=:service_date AND meal_key=:meal_key
                                """
                            ),
                            {"group_id": group_id, "service_date": service_date.isoformat(), "meal_key": meal_key},
                        )
                    touched = True
                    continue

                quantity = _parse_int(clean_value)
                if quantity < 0:
                    raise ValueError("quantity_negative")

                current_quantity = resolve_effective_quantity_in_session(
                    db,
                    group_id,
                    default_quantity,
                    is_active,
                    service_date,
                    meal_key,
                )
                if quantity == current_quantity:
                    continue

                if scope == "forever":
                    db.execute(
                        text(
                            """
                            INSERT INTO department_requirement_group_weekday_overrides(group_id, weekday, meal_key, quantity)
                            VALUES(:group_id, :weekday, :meal_key, :quantity)
                            ON CONFLICT(group_id, weekday, meal_key)
                            DO UPDATE SET quantity=excluded.quantity
                            """
                        ),
                        {"group_id": group_id, "weekday": weekday, "meal_key": meal_key, "quantity": quantity},
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO department_requirement_group_service_overrides(group_id, service_date, meal_key, quantity, created_at, updated_at)
                            VALUES(:group_id, :service_date, :meal_key, :quantity, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT(group_id, service_date, meal_key)
                            DO UPDATE SET quantity=excluded.quantity, updated_at=CURRENT_TIMESTAMP
                            """
                        ),
                        {"group_id": group_id, "service_date": service_date.isoformat(), "meal_key": meal_key, "quantity": quantity},
                    )
                touched = True
    return touched


def _validate_effective_state(db, *, department_id: str, year: int, week: int) -> None:
    from .department_requirement_group_invariant import RequirementCountExceededError, RequirementCountViolation, resolve_effective_special_diet_total_in_session

    residents_by_day = _resident_rows_for_scope_in_session(db, department_id=department_id, year=year, week=week)
    for weekday, service_date in enumerate(_selected_week_dates(year, week), start=1):
        day_residents = residents_by_day.get(weekday, {"lunch": 0, "dinner": 0})
        for meal_key in ("lunch", "dinner"):
            resident_total = int(day_residents.get(meal_key, 0) or 0)
            total_special = int(
                resolve_effective_special_diet_total_in_session(
                    db,
                    department_id,
                    service_date=service_date,
                    meal_key=meal_key,
                )
            )
            if total_special > resident_total:
                raise RequirementCountExceededError(
                    RequirementCountViolation(
                        group_id="",
                        group_name="Registrerade kostbehov",
                        quantity=total_special,
                        resident_count=resident_total,
                        scope="total",
                        service_date=service_date,
                        weekday=weekday,
                        meal_key=meal_key,
                    )
                )


def save_department_variation_submission(
    *,
    department_id: str,
    site_id: str,
    form: Any,
    year: int,
    week: int,
) -> DepartmentVariationSaveResult:
    scope = _normalize_scope(form.get("mode") or form.get("variation_scope") or "week")
    resident_items = _parse_resident_items(form)
    need_cells = _parse_need_cells(form)
    if not resident_items and not need_cells:
        raise ValueError("variation_payload_empty")

    db = get_session()
    try:
        with db.begin():
            _ensure_tables(db)
            department_row = db.execute(
                text("SELECT id FROM departments WHERE id=:department_id AND site_id=:site_id"),
                {"department_id": department_id, "site_id": site_id},
            ).fetchone()
            if department_row is None:
                raise ValueError("department_not_found")

            resident_changes = False
            if resident_items:
                _apply_resident_changes(db, department_id=department_id, scope=scope, year=year, week=week, resident_items=resident_items)
                resident_changes = True

            need_changes = _apply_need_changes(db, department_id=department_id, scope=scope, year=year, week=week, need_cells=need_cells)

            _validate_effective_state(db, department_id=department_id, year=year, week=week)
            return DepartmentVariationSaveResult(
                resident_changes=resident_changes,
                need_changes=need_changes,
                scope=scope,
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


__all__ = [
    "DepartmentVariationSaveResult",
    "build_requirement_group_variation_rows",
    "build_requirement_group_variation_rows_in_session",
    "save_department_variation_submission",
]