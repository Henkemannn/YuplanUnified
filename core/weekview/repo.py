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
            # Residents counts
            rows_c = db.execute(
                text(
                    """
                    SELECT day_of_week, meal, count
                    FROM weekview_residents_count
                    WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                    ORDER BY day_of_week, meal
                    """
                ),
                {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
            ).fetchall()
            counts = [
                {"day_of_week": int(r[0]), "meal": str(r[1]), "count": int(r[2])} for r in rows_c
            ]
            # Alt2 days
            rows_a = db.execute(
                text(
                    """
                    SELECT day_of_week
                    FROM weekview_alt2_flags
                    WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww AND is_alt2=true
                    ORDER BY day_of_week
                    """
                ),
                {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
            ).fetchall()
            alt2_days = [int(r[0]) for r in rows_a]
            payload["department_summaries"].append(
                {
                    "department_id": department_id,
                    "department_name": None,
                    "department_notes": [],
                    "days": [],
                    # Phase B: expose raw marks for client simplicity
                    "marks": marks,
                    # Phase C: additional aggregates
                    "residents_counts": counts,
                    "alt2_days": alt2_days,
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

    def set_residents_counts(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        items: Sequence[dict],
    ) -> int:
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
            for it in items:
                params = {
                    "tid": str(tenant_id),
                    "dep": department_id,
                    "yy": year,
                    "ww": week,
                    "dow": int(it["day_of_week"]),
                    "meal": str(it["meal"]),
                    "cnt": int(it["count"]),
                }
                if dialect == "sqlite":
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_residents_count(tenant_id, department_id, year, week, day_of_week, meal, count)
                            VALUES(:tid, :dep, :yy, :ww, :dow, :meal, :cnt)
                            ON CONFLICT(tenant_id, department_id, year, week, day_of_week, meal)
                            DO UPDATE SET count=excluded.count
                            """
                        ),
                        params,
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_residents_count(tenant_id, department_id, year, week, day_of_week, meal, count)
                            VALUES(:tid, :dep, :yy, :ww, :dow, :meal, :cnt)
                            ON CONFLICT (tenant_id, department_id, year, week, day_of_week, meal)
                            DO UPDATE SET count=EXCLUDED.count, updated_at=now()
                            """
                        ),
                        params,
                    )
            if dialect == "sqlite":
                db.execute(
                    text(
                        """
                        UPDATE weekview_versions SET version=version+1
                        WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                        """
                    ),
                    {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
                )
            db.commit()
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

    def set_alt2_flags(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        days: Sequence[int],
    ) -> int:
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
            day_set = set(int(d) for d in days)
            # Upsert true for provided days
            for d in day_set:
                params = {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week, "dow": d}
                if dialect == "sqlite":
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_alt2_flags(tenant_id, department_id, year, week, day_of_week, is_alt2)
                            VALUES(:tid, :dep, :yy, :ww, :dow, 1)
                            ON CONFLICT(tenant_id, department_id, year, week, day_of_week)
                            DO UPDATE SET is_alt2=1
                            """
                        ),
                        params,
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_alt2_flags(tenant_id, department_id, year, week, day_of_week, is_alt2)
                            VALUES(:tid, :dep, :yy, :ww, :dow, true)
                            ON CONFLICT (tenant_id, department_id, year, week, day_of_week)
                            DO UPDATE SET is_alt2=true, updated_at=now()
                            """
                        ),
                        params,
                    )
            # Remove others (set false by deletion)
            if day_set:
                db.execute(
                    text(
                        """
                        DELETE FROM weekview_alt2_flags
                        WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                          AND day_of_week NOT IN (%s)
                        """ % ",".join(str(d) for d in sorted(day_set))
                    ),
                    {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
                )
            else:
                # If no days provided, clear all for week
                db.execute(
                    text(
                        """
                        DELETE FROM weekview_alt2_flags
                        WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                        """
                    ),
                    {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
                )
            if dialect == "sqlite":
                db.execute(
                    text(
                        """
                        UPDATE weekview_versions SET version=version+1
                        WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww
                        """
                    ),
                    {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week},
                )
            db.commit()
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
