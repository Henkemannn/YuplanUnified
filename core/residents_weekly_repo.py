from __future__ import annotations

from sqlalchemy import text

from .db import get_session


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

    def get_for_week(self, department_id: str, year: int, week: int) -> dict | None:
        db = get_session()
        try:
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
