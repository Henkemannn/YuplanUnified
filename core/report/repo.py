from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import text

from ..db import get_session
from ..weekview.schema import WeekviewSchemaError, verify_weekview_schema


class ReportRepo:
    """Read-only access for report aggregation from weekview tables."""

    def site_exists(self, tenant_id: int | str, site_id: str) -> bool:
        db = get_session()
        try:
            row = db.execute(
                text("SELECT 1 FROM sites WHERE id=:site AND tenant_id=:tid LIMIT 1"),
                {"site": site_id, "tid": int(tenant_id)},
            ).first()
            return row is not None
        finally:
            db.close()

    @staticmethod
    def _verify_schema(db) -> None:
        verify_weekview_schema(db.connection())

    def get_residents(
        self,
        tenant_id: int | str,
        site_id: str,
        year: int,
        week: int,
        department_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = get_session()
        try:
            self._verify_schema(db)
            params = {"tid": int(tenant_id), "site": site_id, "yy": year, "ww": week}
            where = [
                "r.tenant_id=:tid",
                "s.tenant_id=:tid",
                "d.site_id=:site",
                "r.year=:yy",
                "r.week=:ww",
            ]
            if department_id:
                where.append("r.department_id=:dep")
                params["dep"] = department_id
            rows = db.execute(
                text(
                    f"""
                    SELECT r.department_id, r.day_of_week, r.meal, r.count
                    FROM weekview_residents_count AS r
                    JOIN departments AS d ON d.id=r.department_id
                    JOIN sites AS s ON s.id=d.site_id
                    WHERE {' AND '.join(where)}
                    ORDER BY r.department_id, r.day_of_week, r.meal
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
        self,
        tenant_id: int | str,
        site_id: str,
        year: int,
        week: int,
        department_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = get_session()
        try:
            self._verify_schema(db)
            params = {"tid": int(tenant_id), "site": site_id, "yy": year, "ww": week}
            where = [
                "wr.tenant_id=:tid",
                "s.tenant_id=:tid",
                "d.site_id=:site",
                "wr.year=:yy",
                "wr.week=:ww",
                "wr.marked=1",
            ]
            if department_id:
                where.append("wr.department_id=:dep")
                params["dep"] = department_id
            rows = db.execute(
                text(
                    f"""
                    SELECT wr.department_id, wr.day_of_week, wr.meal,
                           wr.diet_type, dt.name
                    FROM weekview_registrations AS wr
                    JOIN departments AS d ON d.id=wr.department_id
                    JOIN sites AS s ON s.id=d.site_id AND s.tenant_id=wr.tenant_id
                    LEFT JOIN dietary_types AS dt
                      ON CAST(dt.id AS TEXT)=wr.diet_type
                     AND dt.tenant_id=wr.tenant_id
                     AND dt.site_id=d.site_id
                    WHERE {' AND '.join(where)}
                    ORDER BY wr.department_id, wr.day_of_week, wr.meal, wr.diet_type
                    """
                ),
                params,
            ).fetchall()
            marks = []
            for row in rows:
                raw_diet_type = str(row[3]).strip()
                reserved_normal = raw_diet_type.casefold() in {"normal", "normalkost"}
                if reserved_normal:
                    diet_type = raw_diet_type.casefold()
                elif row[4] is None or not str(row[4]).strip():
                    raise WeekviewSchemaError("Diet reference incompatible")
                else:
                    diet_type = str(row[4])
                marks.append(
                    {
                        "department_id": str(row[0]),
                        "day_of_week": int(row[1]),
                        "meal": str(row[2]),
                        "diet_type": diet_type,
                        "reserved_normal": reserved_normal,
                    }
                )
            return marks
        finally:
            db.close()

    def get_versions(
        self,
        tenant_id: int | str,
        site_id: str,
        year: int,
        week: int,
        department_id: Optional[str] = None,
    ) -> Tuple[Dict[str, int], int, int]:
        """Return mapping dept->version and (vmax, vsum).

        vmax and vsum are computed across filtered departments (or all departments when department_id is None).
        """
        db = get_session()
        try:
            self._verify_schema(db)
            params = {"tid": int(tenant_id), "site": site_id, "yy": year, "ww": week}
            where = [
                "v.tenant_id=:tid",
                "s.tenant_id=:tid",
                "d.site_id=:site",
                "v.year=:yy",
                "v.week=:ww",
            ]
            if department_id:
                where.append("v.department_id=:dep")
                params["dep"] = department_id
            rows = db.execute(
                text(
                    f"""
                    SELECT v.department_id, v.version
                    FROM weekview_versions AS v
                    JOIN departments AS d ON d.id=v.department_id
                    JOIN sites AS s ON s.id=d.site_id
                    WHERE {' AND '.join(where)}
                    """
                ),
                params,
            ).fetchall()
            mapping = {str(r[0]): int(r[1]) for r in rows}
            if mapping:
                vmax = max(mapping.values())
                vsum = sum(mapping.values())
            else:
                vmax, vsum = 0, 0
            return mapping, vmax, vsum
        finally:
            db.close()

    def department_exists(
        self,
        tenant_id: int | str,
        site_id: str,
        year: int,
        week: int,
        department_id: str,
    ) -> bool:
        db = get_session()
        try:
            self._verify_schema(db)
            # Check versions first, then residents/registrations
            for table in (
                "weekview_versions",
                "weekview_residents_count",
                "weekview_registrations",
            ):
                rec = db.execute(
                    text(
                        f"""
                        SELECT 1
                        FROM {table} AS entry
                        JOIN departments AS d ON d.id=entry.department_id
                        JOIN sites AS s ON s.id=d.site_id
                        WHERE entry.tenant_id=:tid
                          AND s.tenant_id=:tid
                          AND d.site_id=:site
                          AND entry.department_id=:dep
                          AND entry.year=:yy
                          AND entry.week=:ww
                        LIMIT 1
                        """
                    ),
                    {
                        "tid": int(tenant_id),
                        "site": site_id,
                        "dep": department_id,
                        "yy": year,
                        "ww": week,
                    },
                ).fetchone()
                if rec:
                    return True
            return False
        finally:
            db.close()

    def get_dept_meta(self, tenant_id: int | str, department_ids: Iterable[str]) -> Dict[str, Dict[str, Optional[str]]]:
        """Placeholder: return empty meta for now (name/notes unknown)."""
        return {d: {"department_name": None, "notes": None} for d in department_ids}
