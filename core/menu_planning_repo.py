"""Menu Planning Repository - Alt2 management for admin panel.

Provides methods to get and set Alt2 flags for menu planning interface.
Uses existing weekview_alt2_flags table for data persistence.
"""

from __future__ import annotations
from typing import Dict, Optional
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from .db import get_session


class MenuPlanningRepo:
    """Repository for managing Alt2 selections in menu planning."""

    def _table_columns(self, db, table_name: str) -> set[str]:
        try:
            dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
            if dialect == "sqlite":
                rows = db.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
                return {str(r[1]) for r in rows}
            rows = db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name=:t
                    """
                ),
                {"t": table_name},
            ).fetchall()
            return {str(r[0]) for r in rows}
        except Exception:
            return set()

    def _table_exists(self, db, table_name: str) -> bool:
        cols = self._table_columns(db, table_name)
        return len(cols) > 0

    def get_alt2_for_week(self, tenant_id: int | str, year: int, week: int, site_id: Optional[str] = None) -> Dict[str, Dict[str, bool]]:
        """Get Alt2 flags for all departments in a given week scoped to a site.

        Args:
            tenant_id: Tenant ID (kept for compatibility, not used for filtering)
            year: ISO year
            week: ISO week number (1-53)
            site_id: Optional site filter; when provided, limits departments and flags to the site

        Returns:
            Dictionary mapping department_id -> {day_of_week_str: is_alt2_bool}
        """
        db = get_session()
        try:
            cols = self._table_columns(db, "weekview_alt2_flags")
            if not cols:
                return {}

            day_col = "day_of_week" if "day_of_week" in cols else ("weekday" if "weekday" in cols else None)
            enabled_col = "enabled" if "enabled" in cols else ("is_alt2" if "is_alt2" in cols else None)
            if ("department_id" not in cols) or ("year" not in cols) or ("week" not in cols) or (day_col is None) or (enabled_col is None):
                return {}

            where = ["year = :year", "week = :week"]
            params = {"year": year, "week": week}
            if site_id and "site_id" in cols:
                where.append("site_id = :sid")
                params["sid"] = str(site_id)
            elif "tenant_id" in cols and tenant_id is not None:
                where.append("tenant_id = :tid")
                params["tid"] = str(tenant_id)

            sql = (
                f"SELECT department_id, {day_col} AS day_of_week, {enabled_col} AS enabled "
                f"FROM weekview_alt2_flags WHERE {' AND '.join(where)} "
                f"ORDER BY department_id, {day_col}"
            )

            try:
                rows = db.execute(text(sql), params).fetchall()
            except (OperationalError, ProgrammingError) as exc:
                msg = str(exc).lower()
                if "weekview_alt2_flags" in msg and (
                    "no such table" in msg
                    or "does not exist" in msg
                    or "undefined table" in msg
                    or "no such column" in msg
                    or "undefined column" in msg
                ):
                    return {}
                raise

            result: Dict[str, Dict[str, bool]] = {}
            for row in rows:
                dept_id = str(row[0])
                day_of_week = int(row[1])
                enabled = bool(int(row[2]))
                if dept_id not in result:
                    result[dept_id] = {}
                result[dept_id][str(day_of_week)] = enabled
            return result
        finally:
            db.close()
    
    def set_alt2_for_week(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        alt2_map: Dict[str, Dict[str, bool]],
        site_id: Optional[str] = None,
    ) -> None:
        """Set Alt2 flags for departments in a given week.
        
        Args:
            tenant_id: Tenant ID
            year: ISO year
            week: ISO week number (1-53)
            alt2_map: Dictionary mapping department_id -> {day_key: is_alt2_bool}
                     where day_key can be "1"-"7" (day_of_week) or ISO date string
            site_id: Optional site filter (not used in Phase 4)
        
        The method performs an upsert operation using canonical keys:
        (site_id, department_id, year, week, day_of_week).
        """
        db = get_session()
        try:
            # Ensure table exists (defensive for tests) with canonical schema
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
                        site_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        day_of_week INTEGER NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 0,
                        UNIQUE (site_id, department_id, year, week, day_of_week)
                    )
                    """
                )
            )

            cols = self._table_columns(db, "weekview_alt2_flags")
            if not cols:
                db.commit()
                return

            day_col = "day_of_week" if "day_of_week" in cols else ("weekday" if "weekday" in cols else None)
            enabled_col = "enabled" if "enabled" in cols else ("is_alt2" if "is_alt2" in cols else None)
            if ("department_id" not in cols) or ("year" not in cols) or ("week" not in cols) or (day_col is None) or (enabled_col is None):
                db.commit()
                return
            
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
                    
                    value_enabled = 1 if is_alt2 else 0
                    key_where = ["department_id = :dept", "year = :year", "week = :week", f"{day_col} = :dow"]
                    params = {
                        "dept": str(department_id),
                        "year": year,
                        "week": week,
                        "dow": day_of_week,
                        "enabled": value_enabled,
                    }
                    insert_cols = ["department_id", "year", "week", day_col, enabled_col]
                    insert_vals = [":dept", ":year", ":week", ":dow", ":enabled"]

                    if "site_id" in cols:
                        key_where.append("site_id = :sid")
                        params["sid"] = str(site_id or "")
                        insert_cols.append("site_id")
                        insert_vals.append(":sid")
                    elif "tenant_id" in cols and tenant_id is not None:
                        key_where.append("tenant_id = :tid")
                        params["tid"] = str(tenant_id)
                        insert_cols.append("tenant_id")
                        insert_vals.append(":tid")

                    upd = db.execute(
                        text(
                            f"UPDATE weekview_alt2_flags SET {enabled_col} = :enabled "
                            f"WHERE {' AND '.join(key_where)}"
                        ),
                        params,
                    )

                    if int(getattr(upd, "rowcount", 0) or 0) == 0:
                        db.execute(
                            text(
                                f"INSERT INTO weekview_alt2_flags ({', '.join(insert_cols)}) "
                                f"VALUES ({', '.join(insert_vals)})"
                            ),
                            params,
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
                    WHERE year = :year AND week = :week
                    """
                ),
                {"year": year, "week": week},
            )
            db.commit()
        finally:
            db.close()
