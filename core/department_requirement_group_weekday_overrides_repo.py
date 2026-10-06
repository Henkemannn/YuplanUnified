from __future__ import annotations

from datetime import date as _date
from typing import Any

from sqlalchemy import text

from .db import get_session
from .department_requirement_group_invariant import (
    department_fixed_resident_count,
    resolve_effective_special_diet_total_in_session,
    validate_special_diet_total_in_session,
)
from .models import DepartmentRequirementGroup, DepartmentRequirementGroupWeekdayOverride
from .weekview.service import resolve_effective_resident_counts_for_day


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
            result = self.set_override_in_session(db, group_id, weekday, meal_key, quantity)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def set_override_in_session(self, db, group_id: str, weekday: int, meal_key: str, quantity: int) -> dict[str, Any]:
        self._ensure_table(db)
        group = self._load_group(db, group_id)
        group_row = db.execute(
            text(
                """
                SELECT id, label, department_id, is_active
                FROM department_requirement_groups
                WHERE id = :group_id
                """
            ),
            {"group_id": str(group_id)},
        ).fetchone()
        normalized_weekday = _normalize_weekday(weekday)
        normalized_meal_key = _normalize_meal_key(meal_key)
        normalized_quantity = _normalize_quantity(quantity)
        if group_row is not None and bool(group_row[3]):
            current_total = resolve_effective_special_diet_total_in_session(
                db,
                str(group_row[2]),
            )
            existing_row = db.execute(
                text(
                    """
                    SELECT quantity
                    FROM department_requirement_group_weekday_overrides
                    WHERE group_id=:group_id AND weekday=:weekday AND meal_key=:meal_key
                    """
                ),
                {"group_id": str(group_id), "weekday": normalized_weekday, "meal_key": normalized_meal_key},
            ).fetchone()
            current_group_quantity = int(existing_row[0] or 0) if existing_row is not None else int(group.default_quantity or 0)
            validate_special_diet_total_in_session(
                db,
                str(group_row[2]),
                resident_count=int(
                    db.execute(
                        text("SELECT COALESCE(resident_count_fixed, 0) FROM departments WHERE id=:id"),
                        {"id": str(group_row[2])},
                    ).fetchone()[0]
                    or 0
                ),
                expected_total=current_total - current_group_quantity + normalized_quantity,
            )

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
        return {
            "group_id": str(group_id),
            "weekday": normalized_weekday,
            "meal_key": normalized_meal_key,
            "quantity": normalized_quantity,
        }

    def delete_override_in_session(self, db, group_id: str, weekday: int, meal_key: str) -> bool:
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
        return bool(result.rowcount)

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
            result = self.delete_override_in_session(db, group_id, weekday, meal_key)
            db.commit()
            return bool(result)
        except Exception:
            db.rollback()
            raise
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