from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from .db import get_session
from .models import DepartmentMenuRowDemand


def _serialize_row(row) -> dict:
    return {
        "tenant_id": int(row[0]),
        "site_id": str(row[1]),
        "department_id": str(row[2]),
        "year": int(row[3]),
        "week": int(row[4]),
        "weekday": int(row[5]),
        "builder_menu_id": str(row[6]),
        "builder_menu_version": int(row[7]),
        "builder_menu_row_id": str(row[8]),
        "selection_group_id": str(row[9]) if row[9] is not None else None,
        "quantity": int(row[10]),
        "created_at": row[11],
        "updated_at": row[12],
    }


class DepartmentMenuRowDemandRepo:
    def _ensure_table(self, db) -> None:
        DepartmentMenuRowDemand.__table__.create(bind=db.bind, checkfirst=True)

    def get_for_row(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: int,
        builder_menu_id: str,
        builder_menu_version: int,
        builder_menu_row_id: str,
    ) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            row = db.execute(
                text(
                    """
                    SELECT tenant_id, site_id, department_id, year, week, weekday,
                           builder_menu_id, builder_menu_version, builder_menu_row_id,
                           selection_group_id, quantity, created_at, updated_at
                    FROM department_menu_row_demands
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND department_id=:department_id
                      AND year=:year
                      AND week=:week
                      AND weekday=:weekday
                      AND builder_menu_id=:builder_menu_id
                      AND builder_menu_version=:builder_menu_version
                      AND builder_menu_row_id=:builder_menu_row_id
                    """
                ),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                    "weekday": int(weekday),
                    "builder_menu_id": str(builder_menu_id),
                    "builder_menu_version": int(builder_menu_version),
                    "builder_menu_row_id": str(builder_menu_row_id),
                },
            ).fetchone()
            if row is None:
                return None
            return _serialize_row(row)
        finally:
            db.close()

    def upsert_for_row(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: int,
        builder_menu_id: str,
        builder_menu_version: int,
        builder_menu_row_id: str,
        selection_group_id: str | None,
        quantity: int,
    ) -> dict:
        db = get_session()
        try:
            self._ensure_table(db)
            now = datetime.now(UTC)
            existing = db.execute(
                text(
                    """
                    SELECT id FROM department_menu_row_demands
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND department_id=:department_id
                      AND year=:year
                      AND week=:week
                      AND weekday=:weekday
                      AND builder_menu_id=:builder_menu_id
                      AND builder_menu_version=:builder_menu_version
                      AND builder_menu_row_id=:builder_menu_row_id
                    """
                ),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                    "weekday": int(weekday),
                    "builder_menu_id": str(builder_menu_id),
                    "builder_menu_version": int(builder_menu_version),
                    "builder_menu_row_id": str(builder_menu_row_id),
                },
            ).fetchone()
            params = {
                "tenant_id": int(tenant_id),
                "site_id": str(site_id),
                "department_id": str(department_id),
                "year": int(year),
                "week": int(week),
                "weekday": int(weekday),
                "builder_menu_id": str(builder_menu_id),
                "builder_menu_version": int(builder_menu_version),
                "builder_menu_row_id": str(builder_menu_row_id),
                "selection_group_id": str(selection_group_id).strip() if selection_group_id is not None else None,
                "quantity": int(quantity),
                "created_at": now,
                "updated_at": now,
            }
            if existing is None:
                db.execute(
                    text(
                        """
                        INSERT INTO department_menu_row_demands(
                            tenant_id, site_id, department_id, year, week, weekday,
                            builder_menu_id, builder_menu_version, builder_menu_row_id,
                            selection_group_id, quantity, created_at, updated_at
                        ) VALUES(
                            :tenant_id, :site_id, :department_id, :year, :week, :weekday,
                            :builder_menu_id, :builder_menu_version, :builder_menu_row_id,
                            :selection_group_id, :quantity, :created_at, :updated_at
                        )
                        """
                    ),
                    params,
                )
            else:
                db.execute(
                    text(
                        """
                        UPDATE department_menu_row_demands
                        SET selection_group_id=:selection_group_id,
                            quantity=:quantity,
                            updated_at=:updated_at
                        WHERE tenant_id=:tenant_id
                          AND site_id=:site_id
                          AND department_id=:department_id
                          AND year=:year
                          AND week=:week
                          AND weekday=:weekday
                          AND builder_menu_id=:builder_menu_id
                          AND builder_menu_version=:builder_menu_version
                          AND builder_menu_row_id=:builder_menu_row_id
                        """
                    ),
                    params,
                )
            db.commit()
            row = self.get_for_row(
                tenant_id=tenant_id,
                site_id=site_id,
                department_id=department_id,
                year=year,
                week=week,
                weekday=weekday,
                builder_menu_id=builder_menu_id,
                builder_menu_version=builder_menu_version,
                builder_menu_row_id=builder_menu_row_id,
            )
            if row is None:
                return {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                    "weekday": int(weekday),
                    "builder_menu_id": str(builder_menu_id),
                    "builder_menu_version": int(builder_menu_version),
                    "builder_menu_row_id": str(builder_menu_row_id),
                    "selection_group_id": str(selection_group_id).strip() if selection_group_id is not None else None,
                    "quantity": int(quantity),
                    "created_at": now,
                    "updated_at": now,
                }
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_for_department_weekday(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: int,
    ) -> list[dict]:
        db = get_session()
        try:
            self._ensure_table(db)
            rows = db.execute(
                text(
                    """
                    SELECT tenant_id, site_id, department_id, year, week, weekday,
                           builder_menu_id, builder_menu_version, builder_menu_row_id,
                           selection_group_id, quantity, created_at, updated_at
                    FROM department_menu_row_demands
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND department_id=:department_id
                      AND year=:year
                      AND week=:week
                      AND weekday=:weekday
                    ORDER BY builder_menu_id ASC, builder_menu_version ASC, builder_menu_row_id ASC
                    """
                ),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                    "weekday": int(weekday),
                },
            ).fetchall()
            return [_serialize_row(row) for row in rows]
        finally:
            db.close()

    def list_for_selection_group(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        weekday: int,
        selection_group_id: str | None,
    ) -> list[dict]:
        db = get_session()
        try:
            self._ensure_table(db)
            params = {
                "tenant_id": int(tenant_id),
                "site_id": str(site_id),
                "department_id": str(department_id),
                "year": int(year),
                "week": int(week),
                "weekday": int(weekday),
            }
            if selection_group_id is None:
                sql_text = """
                    SELECT tenant_id, site_id, department_id, year, week, weekday,
                           builder_menu_id, builder_menu_version, builder_menu_row_id,
                           selection_group_id, quantity, created_at, updated_at
                    FROM department_menu_row_demands
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND department_id=:department_id
                      AND year=:year
                      AND week=:week
                      AND weekday=:weekday
                      AND selection_group_id IS NULL
                    ORDER BY builder_menu_id ASC, builder_menu_version ASC, builder_menu_row_id ASC
                """
            else:
                sql_text = """
                    SELECT tenant_id, site_id, department_id, year, week, weekday,
                           builder_menu_id, builder_menu_version, builder_menu_row_id,
                           selection_group_id, quantity, created_at, updated_at
                    FROM department_menu_row_demands
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND department_id=:department_id
                      AND year=:year
                      AND week=:week
                      AND weekday=:weekday
                      AND selection_group_id=:selection_group_id
                    ORDER BY builder_menu_id ASC, builder_menu_version ASC, builder_menu_row_id ASC
                """
                params["selection_group_id"] = str(selection_group_id)
            rows = db.execute(text(sql_text), params).fetchall()
            return [_serialize_row(row) for row in rows]
        finally:
            db.close()

    def list_for_builder_menu_row_id(
        self,
        *,
        tenant_id: int,
        site_id: str,
        builder_menu_row_id: str,
    ) -> list[dict]:
        db = get_session()
        try:
            self._ensure_table(db)
            rows = db.execute(
                text(
                    """
                    SELECT tenant_id, site_id, department_id, year, week, weekday,
                           builder_menu_id, builder_menu_version, builder_menu_row_id,
                           selection_group_id, quantity, created_at, updated_at
                    FROM department_menu_row_demands
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND builder_menu_row_id=:builder_menu_row_id
                    ORDER BY department_id ASC, year ASC, week ASC, weekday ASC
                    """
                ),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "builder_menu_row_id": str(builder_menu_row_id),
                },
            ).fetchall()
            return [_serialize_row(row) for row in rows]
        finally:
            db.close()
