from __future__ import annotations

from datetime import UTC, date as _date, datetime as _datetime

from sqlalchemy import text

from .db import get_session
from .models import DepartmentRequirementGroup, DepartmentRequirementGroupServiceOverride


def _normalize_service_date(value) -> _date:
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


def _normalize_meal_key(value) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        raise ValueError("meal_key_empty")
    return raw


def resolve_effective_quantity_in_session(
    db,
    group_id,
    default_quantity,
    is_active,
    service_date,
    meal_key,
) -> int:
    normalized_date = _normalize_service_date(service_date)
    normalized_meal_key = _normalize_meal_key(meal_key)
    if not bool(is_active):
        return 0
    row = db.execute(
        text(
            """
            SELECT quantity
            FROM department_requirement_group_service_overrides
            WHERE group_id = :group_id AND service_date = :service_date AND meal_key = :meal_key
            """
        ),
        {
            "group_id": str(group_id),
            "service_date": normalized_date,
            "meal_key": normalized_meal_key,
        },
    ).fetchone()
    if row is not None:
        return int(row[0] or 0)
    return int(default_quantity or 0)


class DepartmentRequirementGroupServiceOverridesRepo:
    def _ensure_table(self, db) -> None:
        bind = getattr(db, "bind", None)
        if bind is None or getattr(getattr(bind, "dialect", None), "name", "") != "sqlite":
            return
        DepartmentRequirementGroupServiceOverride.__table__.create(bind=bind, checkfirst=True)

    def _normalize_service_date(self, value) -> _date:
        return _normalize_service_date(value)

    def _normalize_meal_key(self, value) -> str:
        return _normalize_meal_key(value)

    def _normalize_quantity(self, value) -> int:
        quantity = int(value)
        if quantity < 0:
            raise ValueError("quantity_negative")
        return quantity

    def _load_group(self, db, group_id: str) -> DepartmentRequirementGroup:
        group = db.get(DepartmentRequirementGroup, str(group_id))
        if group is None:
            raise ValueError("department_requirement_group_not_found")
        return group

    def _get_override_row(self, db, group_id, service_date, meal_key):
        normalized_date = self._normalize_service_date(service_date)
        normalized_meal_key = self._normalize_meal_key(meal_key)
        row = db.execute(
            text(
                """
                SELECT group_id, service_date, meal_key, quantity, created_at, updated_at
                FROM department_requirement_group_service_overrides
                WHERE group_id = :group_id AND service_date = :service_date AND meal_key = :meal_key
                """
            ),
            {
                "group_id": str(group_id),
                "service_date": normalized_date,
                "meal_key": normalized_meal_key,
            },
        ).fetchone()
        return row, normalized_date, normalized_meal_key

    def _serialize_row(self, row) -> dict:
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
            "quantity": int(row[3] or 0),
            "created_at": row[4],
            "updated_at": row[5],
        }

    def set_override(self, group_id, service_date, meal_key, quantity) -> dict:
        db = get_session()
        try:
            self._ensure_table(db)
            self._load_group(db, group_id)
            normalized_date = self._normalize_service_date(service_date)
            normalized_meal_key = self._normalize_meal_key(meal_key)
            normalized_quantity = self._normalize_quantity(quantity)
            now = _datetime.now(UTC).isoformat()
            db.execute(
                text(
                    """
                    INSERT INTO department_requirement_group_service_overrides(
                        group_id, service_date, meal_key, quantity, created_at, updated_at
                    )
                    VALUES(:group_id, :service_date, :meal_key, :quantity, :created_at, :updated_at)
                    ON CONFLICT(group_id, service_date, meal_key)
                    DO UPDATE SET
                        quantity = excluded.quantity,
                        updated_at = excluded.updated_at
                    """
                ),
                {
                    "group_id": str(group_id),
                    "service_date": normalized_date,
                    "meal_key": normalized_meal_key,
                    "quantity": normalized_quantity,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            db.commit()
            row, _, _ = self._get_override_row(db, group_id, normalized_date, normalized_meal_key)
            if row is not None:
                return self._serialize_row(row)
            return {
                "group_id": str(group_id),
                "service_date": normalized_date.isoformat(),
                "meal_key": normalized_meal_key,
                "quantity": normalized_quantity,
                "created_at": now,
                "updated_at": now,
            }
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_override(self, group_id, service_date, meal_key) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            self._load_group(db, group_id)
            row, _, _ = self._get_override_row(db, group_id, service_date, meal_key)
            if row is None:
                return None
            return self._serialize_row(row)
        finally:
            db.close()

    def delete_override(self, group_id, service_date, meal_key) -> bool:
        db = get_session()
        try:
            self._ensure_table(db)
            self._load_group(db, group_id)
            normalized_date = self._normalize_service_date(service_date)
            normalized_meal_key = self._normalize_meal_key(meal_key)
            result = db.execute(
                text(
                    """
                    DELETE FROM department_requirement_group_service_overrides
                    WHERE group_id = :group_id AND service_date = :service_date AND meal_key = :meal_key
                    """
                ),
                {
                    "group_id": str(group_id),
                    "service_date": normalized_date,
                    "meal_key": normalized_meal_key,
                },
            )
            db.commit()
            return int(getattr(result, "rowcount", 0) or 0) > 0
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_for_group(self, group_id, start_date=None, end_date=None) -> list[dict]:
        db = get_session()
        try:
            self._ensure_table(db)
            self._load_group(db, group_id)
            where_clauses = ["group_id = :group_id"]
            params: dict[str, object] = {"group_id": str(group_id)}
            if start_date is not None:
                where_clauses.append("service_date >= :start_date")
                params["start_date"] = self._normalize_service_date(start_date)
            if end_date is not None:
                where_clauses.append("service_date <= :end_date")
                params["end_date"] = self._normalize_service_date(end_date)
            rows = db.execute(
                text(
                    """
                    SELECT group_id, service_date, meal_key, quantity, created_at, updated_at
                    FROM department_requirement_group_service_overrides
                    WHERE {where}
                    ORDER BY service_date ASC, meal_key ASC
                    """.format(where=" AND ".join(where_clauses))
                ),
                params,
            ).fetchall()
            return [self._serialize_row(row) for row in rows]
        finally:
            db.close()

    def resolve_effective_quantity(self, group_id, service_date, meal_key) -> int:
        db = get_session()
        try:
            self._ensure_table(db)
            group = self._load_group(db, group_id)
            return resolve_effective_quantity_in_session(
                db,
                group.id,
                group.default_quantity,
                group.is_active,
                service_date,
                meal_key,
            )
        finally:
            db.close()


__all__ = ["DepartmentRequirementGroupServiceOverridesRepo", "resolve_effective_quantity_in_session"]