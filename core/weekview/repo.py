from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Sequence

from sqlalchemy import text

from ..db import get_session
from ..department_menu_choice_repo import MenuChoiceRepo
from .schema import verify_weekview_schema


_schema_verified: ContextVar[tuple[object, object] | None] = ContextVar(
    "weekview_schema_verified", default=None
)


def _schema_scope(db) -> tuple[object, object]:
    connection = db.connection()
    return db.get_bind(), connection.connection.driver_connection


def _scope_matches(scope: tuple[object, object] | None, db) -> bool:
    if scope is None:
        return False
    bind, driver_connection = _schema_scope(db)
    return scope[0] is bind and scope[1] is driver_connection


class WeekviewRepo:
    """Weekview repository with portable SQL implementation.

    Notes:
    - In production (Postgres), version bump is handled by triggers from the migration.
    - In tests (SQLite), schema is provisioned explicitly and version bumps are emulated.
    """

    @staticmethod
    def _verify_schema_in_session(db) -> None:
        if not _scope_matches(_schema_verified.get(), db):
            verify_weekview_schema(db.connection())

    @contextmanager
    def schema_verified(self):
        db = get_session()
        if _scope_matches(_schema_verified.get(), db):
            yield
            return
        scope = _schema_scope(db)
        try:
            verify_weekview_schema(db.connection())
        except Exception:
            db.close()
            raise
        token = _schema_verified.set(scope)
        try:
            yield
        finally:
            _schema_verified.reset(token)
            db.close()

    def _ensure_version_row_in_session(self, db, tenant_id: int | str, year: int, week: int, department_id: str) -> None:
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

    def get_weekview(
        self, tenant_id: int | str, year: int, week: int, department_id: Optional[str], site_id: str | None = None
    ) -> dict:
        payload = {
            "year": year,
            "week": week,
            "week_start": None,
            "week_end": None,
            "department_summaries": [],
        }
        db = get_session()
        try:
            self._verify_schema_in_session(db)
            if not department_id:
                return payload
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
            # Alt2 days are derived only from canonical explicit department menu choices.
            site_id_val = str(site_id) if site_id else None
            if not site_id_val:
                row_site = db.execute(
                    text("SELECT site_id FROM departments WHERE id=:dep"),
                    {"dep": department_id},
                ).fetchone()
                site_id_val = str(row_site[0]) if row_site and row_site[0] is not None else None
            alt2_days: list[int] = []
            try:
                choice_repo = MenuChoiceRepo()
                choice_map = choice_repo.derive_map(
                    tenant_id=int(tenant_id),
                    site_id=str(site_id_val or ""),
                    department_id=str(department_id),
                    year=year,
                    week=week,
                )
                alt2_days = [dow for dow, key in ((1, "mon"), (2, "tue"), (3, "wed"), (4, "thu"), (5, "fri"), (6, "sat"), (7, "sun")) if choice_map.get(key) == "Alt2"]
            except Exception:
                alt2_days = []
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
        db = get_session()
        try:
            self._verify_schema_in_session(db)
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
                self._ensure_version_row_in_session(db, tenant_id, year, week, department_id)
                db.commit()
                return 0
            return int(rec[0])
        finally:
            db.close()

    def compare_and_bump_version_in_session(
        self,
        db,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        expected_version: int,
    ) -> int | None:
        self._verify_schema_in_session(db)
        self._ensure_version_row_in_session(db, tenant_id, year, week, department_id)
        result = db.execute(
            text(
                """
                UPDATE weekview_versions
                SET version = version + 1
                WHERE tenant_id=:tid AND department_id=:dep AND year=:yy AND week=:ww AND version=:expected_version
                """
            ),
            {
                "tid": str(tenant_id),
                "dep": department_id,
                "yy": year,
                "ww": week,
                "expected_version": int(expected_version),
            },
        )
        if int(getattr(result, "rowcount", 0) or 0) != 1:
            return None
        return int(expected_version) + 1

    def compare_and_bump_version(
        self,
        tenant_id: int | str,
        year: int,
        week: int,
        department_id: str,
        expected_version: int,
    ) -> int | None:
        db = get_session()
        try:
            new_version = self.compare_and_bump_version_in_session(db, tenant_id, year, week, department_id, expected_version)
            if new_version is None:
                db.rollback()
                return None
            db.commit()
            return new_version
        except Exception:
            db.rollback()
            raise
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
        db = get_session()
        try:
            self._verify_schema_in_session(db)
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
        db = get_session()
        try:
            self._verify_schema_in_session(db)
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
        site_id: str | None = None,
    ) -> int:
        db = get_session()
        try:
            self._verify_schema_in_session(db)
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
            # Resolve site_id for canonical writes
            # Prefer provided site_id; otherwise resolve from department (if present)
            site_id_val = str(site_id) if site_id else None
            if not site_id_val:
                row_site = db.execute(
                    text("SELECT site_id FROM departments WHERE id=:dep"),
                    {"dep": department_id},
                ).fetchone()
                site_id_val = str(row_site[0]) if row_site and row_site[0] is not None else None
            if site_id_val:
                MenuChoiceRepo().replace_alt2_days_in_session(
                    db,
                    tenant_id=int(tenant_id),
                    site_id=str(site_id_val),
                    department_id=str(department_id),
                    year=int(year),
                    week=int(week),
                    days=sorted(day_set),
                    meal="lunch",
                )
            # Upsert true for provided days
            for d in day_set:
                params = {"tid": str(tenant_id), "dep": department_id, "yy": year, "ww": week, "dow": d}
                if dialect == "sqlite":
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled)
                            VALUES(:site_id, :dep, :yy, :ww, :dow, 1)
                            ON CONFLICT(site_id, department_id, year, week, day_of_week)
                            DO UPDATE SET enabled=1
                            """
                        ),
                        {"site_id": site_id_val, **params},
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled)
                            VALUES(:site_id, :dep, :yy, :ww, :dow, true)
                            ON CONFLICT (site_id, department_id, year, week, day_of_week)
                            DO UPDATE SET enabled=true, updated_at=now()
                            """
                        ),
                        {"site_id": site_id_val, **params},
                    )
            # Remove others (set false by deletion)
            if day_set:
                db.execute(
                    text(
                        """
                        DELETE FROM weekview_alt2_flags
                        WHERE site_id=:site_id AND department_id=:dep AND year=:yy AND week=:ww
                          AND day_of_week NOT IN (%s)
                        """ % ",".join(str(d) for d in sorted(day_set))
                    ),
                    {"site_id": site_id_val, "dep": department_id, "yy": year, "ww": week},
                )
            else:
                # If no days provided, clear all for week
                db.execute(
                    text(
                        """
                        DELETE FROM weekview_alt2_flags
                        WHERE site_id=:site_id AND department_id=:dep AND year=:yy AND week=:ww
                        """
                    ),
                    {"site_id": site_id_val, "dep": department_id, "yy": year, "ww": week},
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
