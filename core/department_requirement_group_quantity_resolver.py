from __future__ import annotations

from datetime import date as _date
from typing import Any

from sqlalchemy import text

from .db import get_session


def _normalize_service_date(value: Any) -> _date:
    if isinstance(value, _date):
        return value
    if hasattr(value, "date") and callable(value.date):
        return value.date()
    try:
        return _date.fromisoformat(str(value))
    except Exception as exc:
        raise ValueError("service_date_invalid") from exc


def _normalize_meal_key(value: Any) -> str:
    meal_key = str(value or "").strip().lower()
    if not meal_key:
        raise ValueError("meal_key_empty")
    return meal_key


def resolve_effective_quantity(group_id: str, service_date: Any, meal_key: Any) -> int:
    db = get_session()
    try:
        return resolve_effective_quantity_in_session(db, group_id, service_date, meal_key)
    finally:
        db.close()


def resolve_effective_quantity_in_session(db, group_id: str, service_date: Any, meal_key: Any) -> int:
    normalized_date = _normalize_service_date(service_date)
    normalized_meal_key = _normalize_meal_key(meal_key)
    normalized_weekday = int(normalized_date.isoweekday())

    group_row = db.execute(
        text(
            """
            SELECT default_quantity, is_active
            FROM department_requirement_groups
            WHERE id=:group_id
            """
        ),
        {"group_id": str(group_id)},
    ).fetchone()
    if group_row is None:
        raise ValueError("department_requirement_group_not_found")
    if not bool(group_row[1]):
        return 0

    exact_row = db.execute(
        text(
            """
            SELECT quantity
            FROM department_requirement_group_service_overrides
            WHERE group_id=:group_id AND service_date=:service_date AND meal_key=:meal_key
            """
        ),
        {
            "group_id": str(group_id),
            "service_date": normalized_date.isoformat(),
            "meal_key": normalized_meal_key,
        },
    ).fetchone()
    if exact_row is not None:
        return int(exact_row[0])

    weekday_row = db.execute(
        text(
            """
            SELECT quantity
            FROM department_requirement_group_weekday_overrides
            WHERE group_id=:group_id AND weekday=:weekday AND meal_key=:meal_key
            """
        ),
        {"group_id": str(group_id), "weekday": normalized_weekday, "meal_key": normalized_meal_key},
    ).fetchone()
    if weekday_row is not None:
        return int(weekday_row[0])

    return int(group_row[0])


__all__ = ["resolve_effective_quantity", "resolve_effective_quantity_in_session"]