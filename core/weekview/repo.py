from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import text

from ..db import get_session


class WeekviewRepo:
    """Weekview repository with portable SQL implementation.

    Notes:
    - In production (Postgres), version bump is handled by triggers from the migration.
    - In tests (SQLite), we create minimal tables on demand and emulate version bumps.
    """

    def _ensure_schema(self) -> None:
        """Create minimal tables if they don't exist (SQLite/testing safety)."""
        db = get_session()
        try:
            dialect = db.bind.dialect.name if db.bind is not None else ""
            if dialect != "sqlite":
                return  # assume alembic migration applied in real DB
            # SQLite DDL
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
            db.commit()
        finally:
            db.close()

    def get_weekview(
        self, tenant_id: int | str, year: int, week: int, department_id: Optional[str]
    ) -> dict:
        self._ensure_schema()
        payload = {
            "year": year,
            "week": week,
            "week_start": None,
            "week_end": None,
            "department_summaries": [],
        }
        if not department_id:
            return payload
        db = get_session()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT day_of_week, meal, diet_type, marked
                    FROM weekview_registrations
                    WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                    ORDER BY day_of_week, meal, diet_type
                    """
                ),
                {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
            ).fetchall()
            marks = [
                {
                    "day_of_week": int(r[0]),
                    "meal": str(r[1]),
                    "diet_type": str(r[2]),
                    "marked": bool(r[3]),
                }
                for r in rows
            ]
            payload["department_summaries"].append(
                {
                    "department_id": department_id,
                    "department_name": None,
                    "department_notes": [],
                    "days": [],
                    # Phase B: expose raw marks for client simplicity
                    "marks": marks,
                }
            )
            return payload
        finally:
            db.close()

    def get_version(self, tenant_id: int | str, year: int, week: int, department_id: str) -> int:
        self._ensure_schema()
        db = get_session()
        try:
            rec = db.execute(
                text(
                    """
                    SELECT version FROM weekview_versions
                    WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                    """
                ),
                {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
            ).fetchone()
            if rec is None:
                # Seed row version 0
                db.execute(
                    text(
                        """
                        INSERT INTO weekview_versions(tenant_id, department_id, year, week, version)
                        VALUES(:tid, :dep, :yy, :ww, 0)
                        ON CONFLICT(tenant_id, department_id, year, week) DO NOTHING
                        """
                    ),
                    {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
                )
                db.commit()
                return 0
            return int(rec[0])
        finally:
            db.close()

    def apply_operations(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        ops: Sequence[dict],
    ) -> int:
        """Apply batch toggle operations atomically and return new version.

        On Postgres, version bump occurs via triggers. On SQLite, emulate bump.
        """
        self._ensure_schema()
        db = get_session()
        try:
            dialect = db.bind.dialect.name if db.bind is not None else ""
            # Ensure version row exists
            db.execute(
                text(
                    """
                    INSERT INTO weekview_versions(tenant_id, department_id, year, week, version)
                    VALUES(:tid, :dep, :yy, :ww, 0)
                    ON CONFLICT(tenant_id, department_id, year, week) DO NOTHING
                    """
                ),
                {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
            )
            # Upsert registrations
            for op in ops:
                params = {
                    "tid": str(tenant_id),
                    "dep": department_id,
                    "yy": year,
                    "ww": week,
                    "dow": int(op["day_of_week"]),
                    "meal": str(op["meal"]),
                    "diet": str(op["diet_type"]),
                    "marked": 1 if bool(op.get("marked", True)) else 0,
                }
                if dialect == "sqlite":
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_registrations(tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked)
                            VALUES(:tid, :dep, :yy, :ww, :dow, :meal, :diet, :marked)
                            ON CONFLICT(tenant_id, department_id, year, week, day_of_week, meal, diet_type)
                            DO UPDATE SET marked=excluded.marked
                            """
                        ),
                        params,
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_registrations(tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked)
                            VALUES(:tid, :dep, :yy, :ww, :dow, :meal, :diet, :marked)
                            ON CONFLICT (tenant_id, department_id, year, week, day_of_week, meal, diet_type)
                            DO UPDATE SET marked=EXCLUDED.marked, updated_at=now()
                            """
                        ),
                        params,
                    )
            # Emulate version bump on SQLite where triggers aren't present
            if dialect == "sqlite":
                db.execute(
                    text(
                        """
                        UPDATE weekview_versions
                        SET version = version + 1
                        WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                        """
                    ),
                    {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
                )
            db.commit()
            # Read new version
            ver = db.execute(
                text(
                    """
                    SELECT version FROM weekview_versions
                    WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                    """
                ),
                {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
            ).fetchone()
            return int(ver[0]) if ver else 0
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
