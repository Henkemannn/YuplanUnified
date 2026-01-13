from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import text

from ..db import get_session


class ReportRepo:
    """Read-only access for report aggregation from weekview tables."""

    def _ensure_schema(self) -> None:
        """Ensure weekview tables exist in SQLite test env.

        Mirrors WeekviewRepo._ensure_schema for safety when report is used without touching weekview first.
        """
        db = get_session()
        try:
            dialect = db.bind.dialect.name if db.bind is not None else ""
            if dialect != "sqlite":
                return
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS weekview_registrations (
                      tenant_id TEXT NOT NULL,
                      department_id TEXT NOT NULL,
                      year INTEGER NOT NULL,
                      week INTEGER NOT NULL,
                      day_of_week INTEGER NOT NULL,
                      meal TEXT NOT NULL,
                      diet_type TEXT NOT NULL,
                      marked INTEGER NOT NULL DEFAULT 0,
                      UNIQUE (tenant_id, department_id, year, week, day_of_week, meal, diet_type)
                    );
                    """
                )
            )
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS weekview_versions (
                      tenant_id TEXT NOT NULL,
                      department_id TEXT NOT NULL,
                      year INTEGER NOT NULL,
                      week INTEGER NOT NULL,
                      version INTEGER NOT NULL DEFAULT 0,
                      UNIQUE (tenant_id, department_id, year, week)
                    );
                    """
                )
            )
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS weekview_residents_count (
                        tenant_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        day_of_week INTEGER NOT NULL,
                        meal TEXT NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        UNIQUE (tenant_id, department_id, year, week, day_of_week, meal)
                    );
                    """
                )
            )
            db.commit()
        finally:
            db.close()

    def get_residents(
        self, tenant_id: int | str, year: int, week: int, department_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        self._ensure_schema()
        db = get_session()
        try:
            params = {"tid": str(tenant_id), "yy": year, "ww": week}
            where = ["tenant_id=:tid", "year=:yy", "week=:ww"]
            if department_id:
                where.append("department_id=:dep")
                params["dep"] = department_id
            rows = db.execute(
                text(
                    f"""
                    SELECT department_id, day_of_week, meal, count
                    FROM weekview_residents_count
                    WHERE {' AND '.join(where)}
                    ORDER BY department_id, day_of_week, meal
                    """
                ),
                params,
            ).fetchall()
            return [
                {
                    "department_id": str(r[0]),
                    "day_of_week": int(r[1]),
                    "meal": str(r[2]),
                    "count": int(r[3]),
                }
                for r in rows
            ]
        finally:
            db.close()

    def get_marks(
        self, tenant_id: int | str, year: int, week: int, department_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        self._ensure_schema()
        db = get_session()
        try:
            params = {"tid": str(tenant_id), "yy": year, "ww": week}
            where = ["tenant_id=:tid", "year=:yy", "week=:ww", "marked=1"]
            if department_id:
                where.append("department_id=:dep")
                params["dep"] = department_id
            rows = db.execute(
                text(
                    f"""
                    SELECT department_id, day_of_week, meal, diet_type
                    FROM weekview_registrations
                    WHERE {' AND '.join(where)}
                    ORDER BY department_id, day_of_week, meal, diet_type
                    """
                ),
                params,
            ).fetchall()
            return [
                {
                    "department_id": str(r[0]),
                    "day_of_week": int(r[1]),
                    "meal": str(r[2]),
                    "diet_type": str(r[3]),
                }
                for r in rows
            ]
        finally:
            db.close()

    def get_versions(
        self, tenant_id: int | str, year: int, week: int, department_id: Optional[str] = None
    ) -> Tuple[Dict[str, int], int, int]:
        """Return mapping dept->version and (vmax, nsum).
        - `vmax`: maximum version across filtered departments
        - `nsum`: sum of versions across filtered departments (ensures ETag changes on any mutation)
        """
        self._ensure_schema()
        db = get_session()
        try:
            params = {"tid": str(tenant_id), "yy": year, "ww": week}
            where = ["tenant_id=:tid", "year=:yy", "week=:ww"]
            if department_id:
                where.append("department_id=:dep")
                params["dep"] = department_id
            rows = db.execute(
                text(
                    f"""
                    SELECT department_id, version
                    FROM weekview_versions
                    WHERE {' AND '.join(where)}
                    """
                ),
                params,
            ).fetchall()
            mapping = {str(r[0]): int(r[1]) for r in rows}
            if mapping:
                vmax = max(mapping.values())
                nsum = sum(mapping.values())
            else:
                vmax, nsum = 0, 0
            return mapping, vmax, nsum
        finally:
            db.close()

    def department_exists(self, tenant_id: int | str, year: int, week: int, department_id: str) -> bool:
        self._ensure_schema()
        db = get_session()
        try:
            # Check versions first, then residents/registrations
            for table, extra in (
                ("weekview_versions", ""),
                ("weekview_residents_count", ""),
                ("weekview_registrations", ""),
            ):
                rec = db.execute(
                    text(
                        f"""
                        SELECT 1 FROM {table}
                        WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                        LIMIT 1
                        """
                    ),
                    {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
                ).fetchone()
                if rec:
                    return True
            return False
        finally:
            db.close()

    def get_dept_meta(self, tenant_id: int | str, department_ids: Iterable[str]) -> Dict[str, Dict[str, Optional[str]]]:
        """Placeholder: return empty meta for now (name/notes unknown)."""
        return {d: {"department_name": None, "notes": None} for d in department_ids}
