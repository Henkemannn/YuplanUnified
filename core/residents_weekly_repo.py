from __future__ import annotations

from sqlalchemy import text

from .db import get_session


def _is_sqlite(db) -> bool:
    try:
        return (db.bind and db.bind.dialect and db.bind.dialect.name == "sqlite")
    except Exception:
        return True


class ResidentsWeeklyRepo:
    """
    CRUD for weekly resident overrides per department (lunch/dinner).
    Table: department_residents_weekly
    Columns:
      id (TEXT PK for sqlite; else SERIAL/BIGINT may be used by migrations)
      department_id (TEXT)
      year (INTEGER)
      week (INTEGER)
      residents_lunch (INTEGER NULL)
      residents_dinner (INTEGER NULL)
    Unique: (department_id, year, week)
    """

    def _ensure_table(self, db):
        if _is_sqlite(db):
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS department_residents_weekly (
                        id TEXT PRIMARY KEY,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        residents_lunch INTEGER NULL,
                        residents_dinner INTEGER NULL,
                        updated_at TEXT
                    )
                    """
                )
            )
            db.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    ux_dept_res_week ON department_residents_weekly(department_id, year, week)
                    """
                )
            )

    def get_for_week(self, department_id: str, year: int, week: int) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            row = db.execute(
                text(
                    """
                    SELECT residents_lunch, residents_dinner
                    FROM department_residents_weekly
                    WHERE department_id=:d AND year=:y AND week=:w
                    """
                ),
                {"d": department_id, "y": int(year), "w": int(week)},
            ).fetchone()
            if not row:
                return None
            return {"residents_lunch": row[0], "residents_dinner": row[1]}
        finally:
            db.close()

    def upsert_for_week(
        self,
        department_id: str,
        year: int,
        week: int,
        residents_lunch: int | None,
        residents_dinner: int | None,
    ) -> None:
        """Create or update override row for the given week."""
        import uuid

        db = get_session()
        try:
            self._ensure_table(db)
            # Attempt update first
            res = db.execute(
                text(
                    """
                    UPDATE department_residents_weekly
                    SET residents_lunch=:lunch, residents_dinner=:dinner
                    WHERE department_id=:d AND year=:y AND week=:w
                    """
                ),
                {
                    "lunch": residents_lunch,
                    "dinner": residents_dinner,
                    "d": department_id,
                    "y": int(year),
                    "w": int(week),
                },
            )
            if res.rowcount == 0:
                db.execute(
                    text(
                        """
                        INSERT INTO department_residents_weekly(
                          id, department_id, year, week, residents_lunch, residents_dinner
                        ) VALUES (:id, :d, :y, :w, :lunch, :dinner)
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "d": department_id,
                        "y": int(year),
                        "w": int(week),
                        "lunch": residents_lunch,
                        "dinner": residents_dinner,
                    },
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_for_week(self, department_id: str, year: int, week: int) -> None:
        db = get_session()
        try:
            self._ensure_table(db)
            db.execute(
                text(
                    """
                    DELETE FROM department_residents_weekly
                    WHERE department_id=:d AND year=:y AND week=:w
                    """
                ),
                {"d": department_id, "y": int(year), "w": int(week)},
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
