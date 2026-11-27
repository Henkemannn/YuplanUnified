"""
Meal Registration Model & Repository

Minimal domain model for tracking meal registration state per department/day/meal.
This is separate from the existing diet marking system and serves as a staff acknowledgment
that meal prep/planning has been reviewed for a specific day/meal.

Schema:
- meal_registrations table tracks simple "registered" boolean per (site, department, date, meal_type)
- Updated_at for basic conflict detection (optional in Phase 2)
"""
from __future__ import annotations

from datetime import date as _date, datetime
from typing import Sequence

from sqlalchemy import Integer, String, inspect, text

from .db import get_session


class MealRegistrationRepo:
    """Repository for meal registration operations."""

    @staticmethod
    def _verify_schema(db) -> None:
        inspector = inspect(db.connection())
        columns = {column["name"]: column for column in inspector.get_columns("meal_registrations")}
        expected = {
            "id": Integer, "tenant_id": Integer, "site_id": String,
            "department_id": String, "date": String, "meal_type": String,
            "registered": Integer, "updated_at": String,
        }
        keys = ["tenant_id", "site_id", "department_id", "date", "meal_type"]
        if any(name not in columns or not isinstance(columns[name]["type"], kind)
               or (name in (*keys, "registered") and columns[name]["nullable"])
               for name, kind in expected.items()):
            raise RuntimeError("Incompatible meal registrations schema")
        if inspector.get_pk_constraint("meal_registrations").get("constrained_columns") != ["id"]:
            raise RuntimeError("Incompatible meal registrations primary key")
        if db.bind.dialect.name == "sqlite":
            table_info = db.connection().exec_driver_sql("PRAGMA table_info('meal_registrations')").all()
            indexes = db.connection().exec_driver_sql("PRAGMA index_list('meal_registrations')").all()
            id_type = next(row[2] for row in table_info if row[1] == "id")
            if id_type.strip().upper() != "INTEGER" or any(row[3] == "pk" for row in indexes):
                raise RuntimeError("Meal registrations id must be an SQLite rowid alias")
        if db.bind.dialect.name == "postgresql" and not (
            columns["id"].get("identity") or columns["id"].get("default")
        ):
            raise RuntimeError("Meal registrations id must be generated")
        constraints = inspector.get_unique_constraints("meal_registrations")
        indexes = inspector.get_indexes("meal_registrations")
        if not any(item.get("column_names") == keys for item in constraints) and not any(
            item.get("unique") and item.get("column_names") == keys
            and item.get("dialect_options", {}).get(f"{db.bind.dialect.name}_where") is None
            for item in indexes
        ):
            raise RuntimeError("Incompatible meal registrations unique key")

    def get_registrations_for_week(
        self, tenant_id: int | str, site_id: str, department_id: str, year: int, week: int
    ) -> list[dict]:
        """
        Fetch all meal registrations for a given department and ISO week.
        
        Returns list of dicts with keys: date, meal_type, registered, updated_at
        """
        db = get_session()
        try:
            self._verify_schema(db)
            # Compute week start/end dates from ISO week
            from datetime import date as _date, timedelta
            
            # ISO week calculation: first day of week 1 is the Monday of the week containing Jan 4
            jan4 = _date(year, 1, 4)
            week1_monday = jan4 - timedelta(days=jan4.weekday())
            target_monday = week1_monday + timedelta(weeks=week - 1)
            
            dates = [target_monday + timedelta(days=i) for i in range(7)]
            date_strs = [d.isoformat() for d in dates]
            
            placeholders = ",".join([":d" + str(i) for i in range(7)])
            params = {f"d{i}": date_strs[i] for i in range(7)}
            params.update({
                "tenant_id": int(tenant_id),
                "site_id": site_id,
                "department_id": department_id,
            })
            
            rows = db.execute(
                text(f"""
                    SELECT date, meal_type, registered, updated_at
                    FROM meal_registrations
                    WHERE tenant_id = :tenant_id
                      AND site_id = :site_id
                      AND department_id = :department_id
                      AND date IN ({placeholders})
                    ORDER BY date, meal_type
                """),
                params,
            ).fetchall()
            
            return [
                {
                    "date": row[0],
                    "meal_type": row[1],
                    "registered": bool(row[2]),
                    "updated_at": row[3],
                }
                for row in rows
            ]
        finally:
            db.close()

    def upsert_registration(
        self,
        tenant_id: int | str,
        site_id: str,
        department_id: str,
        date_str: str,
        meal_type: str,
        registered: bool,
    ) -> None:
        """
        Insert or update a meal registration.
        
        Args:
            tenant_id: Tenant ID
            site_id: Site ID (UUID string)
            department_id: Department ID (UUID string)
            date_str: ISO date string (YYYY-MM-DD)
            meal_type: "lunch" or "dinner"
            registered: Boolean registration state
        """
        db = get_session()
        try:
            self._verify_schema(db)
            now = datetime.utcnow().isoformat()
            
            # SQLite upsert (ON CONFLICT)
            db.execute(
                text("""
                    INSERT INTO meal_registrations 
                        (tenant_id, site_id, department_id, date, meal_type, registered, updated_at)
                    VALUES 
                        (:tenant_id, :site_id, :department_id, :date, :meal_type, :registered, :updated_at)
                    ON CONFLICT (tenant_id, site_id, department_id, date, meal_type)
                    DO UPDATE SET
                        registered = :registered,
                        updated_at = :updated_at
                """),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": site_id,
                    "department_id": department_id,
                    "date": date_str,
                    "meal_type": meal_type,
                    "registered": int(registered),
                    "updated_at": now,
                },
            )
            db.commit()
        finally:
            db.close()

    def ensure_table_exists(self) -> None:
        """Verify the migration-provisioned table without changing it."""
        db = get_session()
        try:
            self._verify_schema(db)
        finally:
            db.close()
