from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import text

from .db import get_session


@dataclass
class AnnouncementItem:
    id: int
    site_id: str
    message: str
    event_date: date
    event_time: time | None
    show_on_kitchen_dashboard: bool
    is_active: bool
    created_at: datetime | None
    created_by_user_id: int | None


class AnnouncementsRepo:
    def _ensure_schema(self, db) -> None:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS announcements (
                    id INTEGER PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    event_time TEXT NULL,
                    show_on_kitchen_dashboard INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_by_user_id INTEGER NULL
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_announcements_site_date
                ON announcements(site_id, is_active, event_date)
                """
            )
        )

    def list_active_for_site(
        self,
        site_id: str,
        *,
        include_kitchen_only: bool = False,
        today: date | None = None,
        include_past_days: int = 2,
        limit: int = 30,
    ) -> list[AnnouncementItem]:
        if not site_id:
            return []
        ref_day = today or date.today()
        cutoff = ref_day - timedelta(days=max(0, int(include_past_days)))

        db = get_session()
        try:
            self._ensure_schema(db)
            query = (
                """
                SELECT id, site_id, message, event_date, event_time,
                       show_on_kitchen_dashboard, is_active, created_at, created_by_user_id
                FROM announcements
                WHERE site_id=:sid
                  AND is_active=1
                  AND event_date >= :cutoff
                """
            )
            params = {"sid": site_id, "cutoff": cutoff.isoformat(), "lim": int(limit)}
            if include_kitchen_only:
                query += " AND show_on_kitchen_dashboard=1 "
            query += (
                """
                ORDER BY event_date ASC,
                         CASE WHEN event_time IS NULL OR event_time='' THEN 1 ELSE 0 END ASC,
                         event_time ASC,
                         created_at DESC
                LIMIT :lim
                """
            )
            rows = db.execute(text(query), params).fetchall()
        finally:
            db.close()
        return [_row_to_item(r) for r in rows]

    def create(
        self,
        *,
        site_id: str,
        message: str,
        event_date: date,
        event_time: time | None,
        show_on_kitchen_dashboard: bool,
        created_by_user_id: int | None,
    ) -> int:
        if not site_id:
            raise ValueError("site_id is required")
        if not message:
            raise ValueError("message is required")

        db = get_session()
        try:
            self._ensure_schema(db)
            params = {
                "sid": site_id,
                "msg": message,
                "d": event_date.isoformat(),
                "t": event_time.strftime("%H:%M") if event_time else None,
                "k": 1 if show_on_kitchen_dashboard else 0,
                "uid": created_by_user_id,
            }
            dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
            if dialect == "postgresql":
                res = db.execute(
                    text(
                        """
                        INSERT INTO announcements
                        (site_id, message, event_date, event_time, show_on_kitchen_dashboard, created_by_user_id)
                        VALUES (:sid, :msg, :d, :t, :k, :uid)
                        RETURNING id
                        """
                    ),
                    params,
                )
                row = res.fetchone()
                item_id = int(row[0]) if row else 0
            else:
                res = db.execute(
                    text(
                        """
                        INSERT INTO announcements
                        (site_id, message, event_date, event_time, show_on_kitchen_dashboard, created_by_user_id)
                        VALUES (:sid, :msg, :d, :t, :k, :uid)
                        """
                    ),
                    params,
                )
                item_id = int(res.lastrowid or 0)
            db.commit()
            return item_id
        finally:
            db.close()

    def deactivate(self, item_id: int, site_id: str) -> bool:
        if not site_id:
            return False
        db = get_session()
        try:
            self._ensure_schema(db)
            res = db.execute(
                text(
                    """
                    UPDATE announcements
                    SET is_active=0
                    WHERE id=:id AND site_id=:sid
                    """
                ),
                {"id": int(item_id), "sid": site_id},
            )
            db.commit()
            return bool(res.rowcount)
        finally:
            db.close()

    def update(
        self,
        item_id: int,
        *,
        site_id: str,
        message: str,
        event_date: date,
        event_time: time | None,
        show_on_kitchen_dashboard: bool,
    ) -> bool:
        if not site_id:
            return False
        if not message:
            raise ValueError("message is required")

        db = get_session()
        try:
            self._ensure_schema(db)
            res = db.execute(
                text(
                    """
                    UPDATE announcements
                    SET message=:msg,
                        event_date=:d,
                        event_time=:t,
                        show_on_kitchen_dashboard=:k
                    WHERE id=:id
                      AND site_id=:sid
                      AND is_active=1
                    """
                ),
                {
                    "id": int(item_id),
                    "sid": site_id,
                    "msg": message,
                    "d": event_date.isoformat(),
                    "t": event_time.strftime("%H:%M") if event_time else None,
                    "k": 1 if show_on_kitchen_dashboard else 0,
                },
            )
            db.commit()
            return bool(res.rowcount)
        finally:
            db.close()


def _row_to_item(row) -> AnnouncementItem:
    event_date_val = _parse_date(row[3]) or date.today()
    event_time_val = _parse_time(row[4])
    created_at_val = _parse_datetime(row[7])
    return AnnouncementItem(
        id=int(row[0]),
        site_id=str(row[1]),
        message=str(row[2] or ""),
        event_date=event_date_val,
        event_time=event_time_val,
        show_on_kitchen_dashboard=bool(row[5]),
        is_active=bool(row[6]),
        created_at=created_at_val,
        created_by_user_id=int(row[8]) if row[8] is not None else None,
    )


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _parse_time(value) -> time | None:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if len(raw) == 5:
            return time.fromisoformat(raw)
        return time.fromisoformat(raw[:8])
    except Exception:
        return None


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


__all__ = ["AnnouncementItem", "AnnouncementsRepo"]
