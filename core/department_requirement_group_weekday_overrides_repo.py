from __future__ import annotations

from datetime import date as _date
from typing import Any

from sqlalchemy import text

from .db import get_session
from .models import DepartmentRequirementGroup, DepartmentRequirementGroupWeekdayOverride


def _normalize_weekday(value: Any) -> int:
    weekday = int(value)
    if weekday < 1 or weekday > 7:
        raise ValueError("weekday_invalid")
    return weekday


def _normalize_meal_key(value: Any) -> str:
    meal_key = str(value or "").strip().lower()
    if not meal_key:
        raise ValueError("meal_key_empty")
    return meal_key


def _normalize_quantity(value: Any) -> int:
    quantity = int(value)
    if quantity < 0:
        raise ValueError("quantity_negative")
    return quantity


def _serialize_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "group_id": str(row[0]),
        "weekday": int(row[1]),
        "meal_key": str(row[2]),
        "quantity": int(row[3]),
    }


class DepartmentRequirementGroupWeekdayOverridesRepo:
    def _ensure_table(self, db) -> None:
        DepartmentRequirementGroupWeekdayOverride.__table__.create(bind=db.bind, checkfirst=True)

    def _load_group(self, db, group_id: str) -> DepartmentRequirementGroup:
        group = db.get(DepartmentRequirementGroup, str(group_id))
        if group is None:
            raise ValueError("department_requirement_group_not_found")
        return group

    def set_override(self, group_id: str, weekday: int, meal_key: str, quantity: int) -> dict[str, Any]:
        db = get_session()
        try:
            self._ensure_table(db)
            self._load_group(db, group_id)
            normalized_weekday = _normalize_weekday(weekday)
            normalized_meal_key = _normalize_meal_key(meal_key)
            normalized_quantity = _normalize_quantity(quantity)

            db.execute(
                text(
                    """
                    INSERT INTO department_requirement_group_weekday_overrides(group_id, weekday, meal_key, quantity)
                    VALUES(:group_id, :weekday, :meal_key, :quantity)
                    ON CONFLICT(group_id, weekday, meal_key)
                    DO UPDATE SET quantity=excluded.quantity
                    """
                ),
                {
                    "group_id": str(group_id),
                    "weekday": normalized_weekday,
                    "meal_key": normalized_meal_key,
                    "quantity": normalized_quantity,
                },
            )
            db.commit()
            return {
                "group_id": str(group_id),
                "weekday": normalized_weekday,
                "meal_key": normalized_meal_key,
                "quantity": normalized_quantity,
            }
        finally:
            db.close()

    def get_override(self, group_id: str, weekday: int, meal_key: str) -> dict[str, Any] | None:
        db = get_session()
        try:
            self._ensure_table(db)
            normalized_weekday = _normalize_weekday(weekday)
            normalized_meal_key = _normalize_meal_key(meal_key)
            row = db.execute(
                text(
                    """
                    SELECT group_id, weekday, meal_key, quantity
                    FROM department_requirement_group_weekday_overrides
                    WHERE group_id=:group_id AND weekday=:weekday AND meal_key=:meal_key
                    """
                ),
                {"group_id": str(group_id), "weekday": normalized_weekday, "meal_key": normalized_meal_key},
            ).fetchone()
            return None if row is None else _serialize_row(row)
        finally:
            db.close()

    def delete_override(self, group_id: str, weekday: int, meal_key: str) -> bool:
        db = get_session()
        try:
            self._ensure_table(db)
            normalized_weekday = _normalize_weekday(weekday)
            normalized_meal_key = _normalize_meal_key(meal_key)
            result = db.execute(
                text(
                    """
                    DELETE FROM department_requirement_group_weekday_overrides
                    WHERE group_id=:group_id AND weekday=:weekday AND meal_key=:meal_key
                    """
                ),
                {"group_id": str(group_id), "weekday": normalized_weekday, "meal_key": normalized_meal_key},
            )
            db.commit()
            return bool(result.rowcount)
        finally:
            db.close()

    def list_for_group(self, group_id: str) -> list[dict[str, Any]]:
        db = get_session()
        try:
            self._ensure_table(db)
            rows = db.execute(
                text(
                    """
                    SELECT group_id, weekday, meal_key, quantity
                    FROM department_requirement_group_weekday_overrides
                    WHERE group_id=:group_id
                    ORDER BY weekday ASC, meal_key ASC
                    """
                ),
                {"group_id": str(group_id)},
            ).fetchall()
            return [_serialize_row(row) for row in rows]
        finally:
            db.close()

    def resolve_effective_quantity(self, group_id: str, weekday: int, meal_key: str, default_quantity: int) -> int:
        override = self.get_override(group_id, weekday, meal_key)
        if override is not None:
            return int(override["quantity"])
        return int(default_quantity)


def resolve_effective_quantity_for_weekday(group_id: str, weekday: int, meal_key: str, default_quantity: int) -> int:
    return DepartmentRequirementGroupWeekdayOverridesRepo().resolve_effective_quantity(
        group_id,
        weekday,
        meal_key,
        default_quantity,
    )


__all__ = [
    "DepartmentRequirementGroupWeekdayOverridesRepo",
    "resolve_effective_quantity_for_weekday",
]