from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from .db import get_session
from .models import DepartmentPortalWeekSubmission


class DepartmentPortalWeekSubmissionRepo:
    def _ensure_table(self, db) -> None:
        DepartmentPortalWeekSubmission.__table__.create(bind=db.bind, checkfirst=True)

    def get_for_week(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
    ) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            row = db.execute(
                text(
                    """
                    SELECT tenant_id, site_id, department_id, year, week, builder_menu_id,
                           builder_menu_version, choice_signature, submitted_at, updated_at
                    FROM department_portal_week_submissions
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND department_id=:department_id
                      AND year=:year
                      AND week=:week
                    """
                ),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                },
            ).fetchone()
            if row is None:
                return None
            return {
                "tenant_id": int(row[0]),
                "site_id": str(row[1]),
                "department_id": str(row[2]),
                "year": int(row[3]),
                "week": int(row[4]),
                "builder_menu_id": str(row[5]),
                "builder_menu_version": int(row[6]),
                "choice_signature": str(row[7]),
                "submitted_at": row[8],
                "updated_at": row[9],
            }
        finally:
            db.close()

    def upsert_for_week(
        self,
        *,
        tenant_id: int,
        site_id: str,
        department_id: str,
        year: int,
        week: int,
        builder_menu_id: str,
        builder_menu_version: int,
        choice_signature: str,
    ) -> dict:
        db = get_session()
        try:
            self._ensure_table(db)
            now = datetime.now(UTC)
            existing = db.execute(
                text(
                    """
                    SELECT id FROM department_portal_week_submissions
                    WHERE tenant_id=:tenant_id
                      AND site_id=:site_id
                      AND department_id=:department_id
                      AND year=:year
                      AND week=:week
                    """
                ),
                {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                },
            ).fetchone()
            params = {
                "tenant_id": int(tenant_id),
                "site_id": str(site_id),
                "department_id": str(department_id),
                "year": int(year),
                "week": int(week),
                "builder_menu_id": str(builder_menu_id),
                "builder_menu_version": int(builder_menu_version),
                "choice_signature": str(choice_signature),
                "submitted_at": now,
                "updated_at": now,
            }
            if existing is None:
                db.execute(
                    text(
                        """
                        INSERT INTO department_portal_week_submissions(
                            tenant_id, site_id, department_id, year, week,
                            builder_menu_id, builder_menu_version, choice_signature,
                            submitted_at, updated_at
                        ) VALUES(
                            :tenant_id, :site_id, :department_id, :year, :week,
                            :builder_menu_id, :builder_menu_version, :choice_signature,
                            :submitted_at, :updated_at
                        )
                        """
                    ),
                    params,
                )
            else:
                db.execute(
                    text(
                        """
                        UPDATE department_portal_week_submissions
                        SET builder_menu_id=:builder_menu_id,
                            builder_menu_version=:builder_menu_version,
                            choice_signature=:choice_signature,
                            submitted_at=:submitted_at,
                            updated_at=:updated_at
                        WHERE tenant_id=:tenant_id
                          AND site_id=:site_id
                          AND department_id=:department_id
                          AND year=:year
                          AND week=:week
                        """
                    ),
                    params,
                )
            db.commit()
            row = self.get_for_week(
                tenant_id=tenant_id,
                site_id=site_id,
                department_id=department_id,
                year=year,
                week=week,
            )
            if row is None:
                return {
                    "tenant_id": int(tenant_id),
                    "site_id": str(site_id),
                    "department_id": str(department_id),
                    "year": int(year),
                    "week": int(week),
                    "builder_menu_id": str(builder_menu_id),
                    "builder_menu_version": int(builder_menu_version),
                    "choice_signature": str(choice_signature),
                    "submitted_at": now,
                    "updated_at": now,
                }
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()