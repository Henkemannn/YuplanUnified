from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text

from .db import get_session


class ProductionListsRepo:
    def _ensure_table(self, db) -> None:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS production_lists (
                    id TEXT PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    created_at TEXT,
                    date TEXT NOT NULL,
                    meal_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
        )

    def _cleanup_old_db(self, db, days: int = 7) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=int(days))).strftime("%Y-%m-%dT%H:%M:%S")
        res = db.execute(
            text("DELETE FROM production_lists WHERE COALESCE(created_at, '') < :cutoff"),
            {"cutoff": cutoff},
        )
        return int(res.rowcount or 0)

    @staticmethod
    def _is_missing_table_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return (
            "no such table" in msg and "production_lists" in msg
        ) or (
            "relation" in msg and "production_lists" in msg and "does not exist" in msg
        )

    def cleanup_old(self, days: int = 7) -> int:
        db = get_session()
        try:
            deleted = self._cleanup_old_db(db, days=days)
            db.commit()
            return deleted
        except Exception as e:
            if self._is_missing_table_error(e):
                db.rollback()
                self._ensure_table(db)
                deleted = self._cleanup_old_db(db, days=days)
                db.commit()
                return deleted
            db.rollback()
            raise
        finally:
            db.close()

    def create_snapshot(self, site_id: str, date_iso: str, meal_type: str, payload: dict) -> dict:
        db = get_session()
        try:
            self._cleanup_old_db(db, days=7)
            pid = str(uuid.uuid4())
            created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            db.execute(
                text(
                    """
                    INSERT INTO production_lists(id, site_id, created_at, date, meal_type, payload_json)
                    VALUES(:id, :site_id, :created_at, :date, :meal_type, :payload_json)
                    """
                ),
                {
                    "id": pid,
                    "site_id": str(site_id),
                    "created_at": created_at,
                    "date": str(date_iso),
                    "meal_type": str(meal_type),
                    "payload_json": json.dumps(payload, ensure_ascii=True),
                },
            )
            db.commit()
            return {"id": pid, "site_id": str(site_id), "created_at": created_at, "date": str(date_iso), "meal_type": str(meal_type)}
        except Exception as e:
            if self._is_missing_table_error(e):
                db.rollback()
                self._ensure_table(db)
                self._cleanup_old_db(db, days=7)
                pid = str(uuid.uuid4())
                created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                db.execute(
                    text(
                        """
                        INSERT INTO production_lists(id, site_id, created_at, date, meal_type, payload_json)
                        VALUES(:id, :site_id, :created_at, :date, :meal_type, :payload_json)
                        """
                    ),
                    {
                        "id": pid,
                        "site_id": str(site_id),
                        "created_at": created_at,
                        "date": str(date_iso),
                        "meal_type": str(meal_type),
                        "payload_json": json.dumps(payload, ensure_ascii=True),
                    },
                )
                db.commit()
                return {"id": pid, "site_id": str(site_id), "created_at": created_at, "date": str(date_iso), "meal_type": str(meal_type)}
            db.rollback()
            raise
        finally:
            db.close()

    def list_for_site(self, site_id: str) -> list[dict]:
        db = get_session()
        try:
            self._cleanup_old_db(db, days=7)
            db.commit()
            rows = db.execute(
                text(
                    """
                    SELECT id, site_id, created_at, date, meal_type
                    FROM production_lists
                    WHERE site_id=:site_id
                    ORDER BY created_at DESC
                    """
                ),
                {"site_id": str(site_id)},
            ).fetchall()
            return [
                {
                    "id": str(r[0]),
                    "site_id": str(r[1]),
                    "created_at": str(r[2] or ""),
                    "date": str(r[3]),
                    "meal_type": str(r[4]),
                }
                for r in rows
            ]
        except Exception as e:
            if self._is_missing_table_error(e):
                db.rollback()
                self._ensure_table(db)
                db.commit()
                return []
            raise
        finally:
            db.close()

    def get_for_site(self, list_id: str, site_id: str) -> dict | None:
        db = get_session()
        try:
            self._cleanup_old_db(db, days=7)
            db.commit()
            row = db.execute(
                text(
                    """
                    SELECT id, site_id, created_at, date, meal_type, payload_json
                    FROM production_lists
                    WHERE id=:id AND site_id=:site_id
                    LIMIT 1
                    """
                ),
                {"id": str(list_id), "site_id": str(site_id)},
            ).fetchone()
            if not row:
                return None
            payload = {}
            try:
                payload = json.loads(str(row[5] or "{}"))
            except Exception:
                payload = {}
            return {
                "id": str(row[0]),
                "site_id": str(row[1]),
                "created_at": str(row[2] or ""),
                "date": str(row[3]),
                "meal_type": str(row[4]),
                "payload": payload,
            }
        except Exception as e:
            if self._is_missing_table_error(e):
                db.rollback()
                self._ensure_table(db)
                db.commit()
                return None
            raise
        finally:
            db.close()
