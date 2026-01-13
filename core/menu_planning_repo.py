"""Menu Planning Repository - Alt2 management for admin panel.

Provides methods to get and set Alt2 flags for menu planning interface.
Uses existing weekview_alt2_flags table for data persistence.
"""

from __future__ import annotations
from typing import Dict, Optional
from sqlalchemy import text

from .db import get_session


class MenuPlanningRepo:
    """Repository for managing Alt2 selections in menu planning."""
    
    def get_alt2_for_week(self, tenant_id: int | str, year: int, week: int, site_id: Optional[str] = None) -> Dict[str, Dict[str, bool]]:
        """Get Alt2 flags for all departments in a given week.
        
        Args:
            tenant_id: Tenant ID
            year: ISO year
            week: ISO week number (1-53)
            site_id: Optional site filter (not used in Phase 4, reserved for future)
        
        Returns:
            Dictionary mapping department_id -> {date: is_alt2_bool}
            Example: {
                "dept-uuid-1": {"2025-11-03": True, "2025-11-05": False, ...},
                "dept-uuid-2": {"2025-11-03": False, ...}
            }
        """
        db = get_session()
        try:
            # Query all alt2 flags for the week
            rows = db.execute(
                text(
                    """
                    SELECT department_id, day_of_week, is_alt2
                    FROM weekview_alt2_flags
                    WHERE tenant_id = :tid AND year = :year AND week = :week
                    ORDER BY department_id, day_of_week
                    """
                ),
                {"tid": str(tenant_id), "year": year, "week": week}
            ).fetchall()
            
            # Build result map
            result: Dict[str, Dict[str, bool]] = {}
            for row in rows:
                dept_id = str(row[0])
                day_of_week = int(row[1])
                is_alt2 = bool(row[2])
                
                if dept_id not in result:
                    result[dept_id] = {}
                
                # Convert day_of_week (1-7) to date string
                # For now, store by day_of_week key (will convert to date in service layer)
                result[dept_id][str(day_of_week)] = is_alt2
            
            return result
        finally:
            db.close()
    
    def set_alt2_for_week(
        self, 
        tenant_id: int | str,
        year: int,
        week: int,
        alt2_map: Dict[str, Dict[str, bool]],
        site_id: Optional[str] = None
    ) -> None:
        """Set Alt2 flags for departments in a given week.
        
        Args:
            tenant_id: Tenant ID
            year: ISO year
            week: ISO week number (1-53)
            alt2_map: Dictionary mapping department_id -> {day_key: is_alt2_bool}
                     where day_key can be "1"-"7" (day_of_week) or ISO date string
            site_id: Optional site filter (not used in Phase 4)
        
        The method performs an upsert operation - it will insert new records or update
        existing ones based on the (tenant_id, department_id, year, week, day_of_week) key.
        """
        db = get_session()
        try:
            # Ensure table exists (defensive for tests)
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
                        tenant_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        day_of_week INTEGER NOT NULL,
                        is_alt2 INTEGER NOT NULL DEFAULT 0,
                        UNIQUE (tenant_id, department_id, year, week, day_of_week)
                    )
                    """
                )
            )
            
            # Process each department's alt2 settings
            for department_id, day_flags in alt2_map.items():
                for day_key, is_alt2 in day_flags.items():
                    # Parse day_key - can be "1"-"7" or date string
                    try:
                        day_of_week = int(day_key)
                    except ValueError:
                        # If it's a date string, extract day of week
                        # For now, skip invalid keys
                        continue
                    
                    if day_of_week < 1 or day_of_week > 7:
                        continue
                    
                    # Upsert the flag
                    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
                    
                    if dialect == "sqlite":
                        db.execute(
                            text(
                                """
                                INSERT INTO weekview_alt2_flags 
                                (tenant_id, department_id, year, week, day_of_week, is_alt2)
                                VALUES (:tid, :dept, :year, :week, :dow, :alt2)
                                ON CONFLICT(tenant_id, department_id, year, week, day_of_week)
                                DO UPDATE SET is_alt2 = excluded.is_alt2
                                """
                            ),
                            {
                                "tid": str(tenant_id),
                                "dept": str(department_id),
                                "year": year,
                                "week": week,
                                "dow": day_of_week,
                                "alt2": 1 if is_alt2 else 0
                            }
                        )
                    else:
                        # PostgreSQL
                        db.execute(
                            text(
                                """
                                INSERT INTO weekview_alt2_flags 
                                (tenant_id, department_id, year, week, day_of_week, is_alt2)
                                VALUES (:tid, :dept, :year, :week, :dow, :alt2)
                                ON CONFLICT(tenant_id, department_id, year, week, day_of_week)
                                DO UPDATE SET is_alt2 = EXCLUDED.is_alt2
                                """
                            ),
                            {
                                "tid": str(tenant_id),
                                "dept": str(department_id),
                                "year": year,
                                "week": week,
                                "dow": day_of_week,
                                "alt2": is_alt2
                            }
                        )
            
            db.commit()
        finally:
            db.close()
    
    def clear_alt2_for_week(self, tenant_id: int | str, year: int, week: int) -> None:
        """Clear all Alt2 flags for a given week (utility method for tests).
        
        Args:
            tenant_id: Tenant ID
            year: ISO year
            week: ISO week number
        """
        db = get_session()
        try:
            db.execute(
                text(
                    """
                    DELETE FROM weekview_alt2_flags
                    WHERE tenant_id = :tid AND year = :year AND week = :week
                    """
                ),
                {"tid": str(tenant_id), "year": year, "week": week}
            )
            db.commit()
        finally:
            db.close()
