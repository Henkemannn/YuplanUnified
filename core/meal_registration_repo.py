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

from sqlalchemy import text

from .db import get_session


class MealRegistrationRepo:
    """Repository for meal registration operations."""

    def get_registrations_for_week(
        self, tenant_id: int | str, site_id: str, department_id: str, year: int, week: int
    ) -> list[dict]:
        """
        Fetch all meal registrations for a given department and ISO week.
        
        Returns list of dicts with keys: date, meal_type, registered, updated_at
        """
        db = get_session()
        try:
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
                    "registered": registered,
                    "updated_at": now,
                },
            )
            db.commit()
        finally:
            db.close()

    def ensure_table_exists(self) -> None:
        """
        Ensure the meal_registrations table exists (for test/dev environments).
        Production should use Alembic migrations.
        """
        db = get_session()
        try:
            db.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS meal_registrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NOT NULL,
                        site_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        meal_type TEXT NOT NULL,
                        registered INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT,
                        UNIQUE(tenant_id, site_id, department_id, date, meal_type)
                    )
                """)
            )
            db.commit()
        finally:
            db.close()
