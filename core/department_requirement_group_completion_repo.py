from __future__ import annotations

from datetime import date as _date, datetime as _datetime
from typing import Any

from sqlalchemy import text

from .db import get_session
from .models import DepartmentRequirementGroup, DepartmentRequirementGroupCompletion


def _normalize_service_date(value: Any) -> _date:
    if isinstance(value, _datetime):
        raise ValueError("service_date_invalid")
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("service_date_invalid")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:
        raise ValueError("service_date_invalid") from exc


def _normalize_meal_key(value: Any) -> str:
    meal_key = str(value or "").strip().lower()
    if meal_key not in {"lunch", "dinner"}:
        raise ValueError("meal_key_invalid")
    return meal_key


def _serialize_row(row: tuple[Any, ...]) -> dict[str, Any]:
    service_date = row[1]
    if isinstance(service_date, _datetime):
        service_date_value = service_date.date().isoformat()
    elif isinstance(service_date, _date):
        service_date_value = service_date.isoformat()
    else:
        service_date_value = str(service_date)
    return {
        "group_id": str(row[0]),
        "service_date": service_date_value,
        "meal_key": str(row[2]),
        "marked": bool(row[3]),
    }


class DepartmentRequirementGroupCompletionRepo:
    def _ensure_table(self, db) -> None:
        DepartmentRequirementGroupCompletion.__table__.create(bind=db.bind, checkfirst=True)

    def _load_group(self, db, group_id: str) -> DepartmentRequirementGroup:
        group = db.get(DepartmentRequirementGroup, str(group_id))
        if group is None:
            raise ValueError("department_requirement_group_not_found")
        return group

    def _load_owned_group(self, db, department_id: str, group_id: str) -> DepartmentRequirementGroup:
        group = self._load_group(db, group_id)
        if str(group.department_id) != str(department_id):
            raise ValueError("department_requirement_group_not_owned")
        return group

    def get(self, group_id: str, service_date: Any, meal_key: Any) -> dict[str, Any] | None:
        db = get_session()
        try:
            self._ensure_table(db)
            self._load_group(db, group_id)
            normalized_date = _normalize_service_date(service_date)
            normalized_meal_key = _normalize_meal_key(meal_key)
            row = db.execute(
                text(
                    """
                    SELECT group_id, service_date, meal_key, marked
                    FROM department_requirement_group_completions
                    WHERE group_id=:group_id AND service_date=:service_date AND meal_key=:meal_key
                    """
                ),
                {
                    "group_id": str(group_id),
                    "service_date": normalized_date,
                    "meal_key": normalized_meal_key,
                },
            ).fetchone()
            return None if row is None else _serialize_row(row)
        finally:
            db.close()

    def set_marked(self, department_id: str, group_id: str, service_date: Any, meal_key: Any, marked: bool) -> dict[str, Any]:
        db = get_session()
        try:
            self._ensure_table(db)
            self._load_owned_group(db, department_id, group_id)
            normalized_date = _normalize_service_date(service_date)
            normalized_meal_key = _normalize_meal_key(meal_key)
            normalized_marked = bool(marked)
            db.execute(
                text(
                    """
                    INSERT INTO department_requirement_group_completions(group_id, service_date, meal_key, marked)
                    VALUES(:group_id, :service_date, :meal_key, :marked)
                    ON CONFLICT(group_id, service_date, meal_key)
                    DO UPDATE SET marked=excluded.marked
                    """
                ),
                {
                    "group_id": str(group_id),
                    "service_date": normalized_date,
                    "meal_key": normalized_meal_key,
                    "marked": 1 if normalized_marked else 0,
                },
            )
            db.commit()
            row = db.execute(
                text(
                    """
                    SELECT group_id, service_date, meal_key, marked
                    FROM department_requirement_group_completions
                    WHERE group_id=:group_id AND service_date=:service_date AND meal_key=:meal_key
                    """
                ),
                {
                    "group_id": str(group_id),
                    "service_date": normalized_date,
                    "meal_key": normalized_meal_key,
                },
            ).fetchone()
            if row is None:
                return {
                    "group_id": str(group_id),
                    "service_date": normalized_date.isoformat(),
                    "meal_key": normalized_meal_key,
                    "marked": normalized_marked,
                }
            return _serialize_row(row)
        finally:
            db.close()

    def list_for_department_date_range(
        self,
        department_id: str,
        start_date: Any | None = None,
        end_date: Any | None = None,
        meal_key: Any | None = None,
    ) -> list[dict[str, Any]]:
        db = get_session()
        try:
            self._ensure_table(db)
            where = ["g.department_id=:department_id"]
            params: dict[str, Any] = {"department_id": str(department_id)}
            if start_date is not None:
                where.append("c.service_date >= :start_date")
                params["start_date"] = _normalize_service_date(start_date)
            if end_date is not None:
                where.append("c.service_date <= :end_date")
                params["end_date"] = _normalize_service_date(end_date)
            if meal_key is not None:
                where.append("c.meal_key = :meal_key")
                params["meal_key"] = _normalize_meal_key(meal_key)
            rows = db.execute(
                text(
                    f"""
                    SELECT c.group_id, c.service_date, c.meal_key, c.marked
                    FROM department_requirement_group_completions c
                    JOIN department_requirement_groups g ON g.id = c.group_id
                    WHERE {' AND '.join(where)}
                    ORDER BY c.service_date ASC, c.meal_key ASC, c.group_id ASC
                    """
                ),
                params,
            ).fetchall()
            return [_serialize_row(row) for row in rows]
        finally:
            db.close()


__all__ = ["DepartmentRequirementGroupCompletionRepo"]