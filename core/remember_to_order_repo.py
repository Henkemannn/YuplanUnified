from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import text

from .db import get_session
from .week_key import normalize_week_key


@dataclass
class RememberToOrderItem:
    id: int
    site_id: str
    week_key: str
    text: str
    created_at: datetime | None
    created_by_user_id: int | None
    created_by_role: str
    checked_at: datetime | None
    checked_by_user_id: int | None


class RememberToOrderRepo:
    def _ensure_schema(self, db) -> None:
        try:
            if db.bind and db.bind.dialect.name != "sqlite":
                return
        except Exception:
            return
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS remember_to_order_items (
                    id INTEGER PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    week_key TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_by_user_id INTEGER NULL,
                    created_by_role TEXT NOT NULL,
                    checked_at TEXT NULL,
                    checked_by_user_id INTEGER NULL
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_remember_to_order_items_site_week_checked
                ON remember_to_order_items(site_id, week_key, checked_at)
                """
            )
        )

    def list_visible(self, site_id: str, week_key: str, now: datetime | None = None) -> list[RememberToOrderItem]:
        wk = normalize_week_key(week_key)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        cutoff = current - timedelta(days=2)

        db = get_session()
        try:
            self._ensure_schema(db)
            rows = db.execute(
                text(
                    """
                    SELECT id, site_id, week_key, text, created_at, created_by_user_id, created_by_role,
                           checked_at, checked_by_user_id
                    FROM remember_to_order_items
                    WHERE site_id=:sid AND week_key=:wk
                    """
                ),
                {"sid": site_id, "wk": wk},
            ).fetchall()
        finally:
            db.close()

        items = []
        for r in rows:
            created_at = _parse_dt(r[4])
            checked_at = _parse_dt(r[7])
            if checked_at is not None and checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=timezone.utc)
            if checked_at is None or checked_at >= cutoff:
                items.append(
                    RememberToOrderItem(
                        id=int(r[0]),
                        site_id=str(r[1]),
                        week_key=str(r[2]),
                        text=str(r[3]),
                        created_at=created_at,
                        created_by_user_id=int(r[5]) if r[5] is not None else None,
                        created_by_role=str(r[6] or ""),
                        checked_at=checked_at,
                        checked_by_user_id=int(r[8]) if r[8] is not None else None,
                    )
                )

        unchecked = [it for it in items if it.checked_at is None]
        checked = [it for it in items if it.checked_at is not None]
        unchecked.sort(key=lambda it: (it.created_at or datetime.min.replace(tzinfo=timezone.utc)))
        checked.sort(key=lambda it: (it.checked_at or datetime.min.replace(tzinfo=timezone.utc)))
        return unchecked + checked

    def add(
        self,
        site_id: str,
        week_key: str,
        text_val: str,
        created_by_user_id: int | None,
        created_by_role: str,
        now: datetime | None = None,
    ) -> RememberToOrderItem:
        wk = normalize_week_key(week_key)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)

        db = get_session()
        try:
            self._ensure_schema(db)
            params = {
                "sid": site_id,
                "wk": wk,
                "text": text_val,
                "created_at": current,
                "created_by_user_id": created_by_user_id,
                "created_by_role": created_by_role,
            }
            dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
            if dialect == "postgresql":
                res = db.execute(
                    text(
                        """
                        INSERT INTO remember_to_order_items
                        (site_id, week_key, text, created_at, created_by_user_id, created_by_role)
                        VALUES (:sid, :wk, :text, :created_at, :created_by_user_id, :created_by_role)
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
                        INSERT INTO remember_to_order_items
                        (site_id, week_key, text, created_at, created_by_user_id, created_by_role)
                        VALUES (:sid, :wk, :text, :created_at, :created_by_user_id, :created_by_role)
                        """
                    ),
                    params,
                )
                item_id = int(res.lastrowid or 0)
            db.commit()
        finally:
            db.close()

        return RememberToOrderItem(
            id=int(item_id),
            site_id=site_id,
            week_key=wk,
            text=text_val,
            created_at=current,
            created_by_user_id=created_by_user_id,
            created_by_role=created_by_role,
            checked_at=None,
            checked_by_user_id=None,
        )

    def set_checked(
        self,
        item_id: int,
        checked: bool,
        user_id: int | None,
        now: datetime | None = None,
    ) -> bool:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)

        db = get_session()
        try:
            self._ensure_schema(db)
            if checked:
                res = db.execute(
                    text(
                        """
                        UPDATE remember_to_order_items
                        SET checked_at=:checked_at, checked_by_user_id=:checked_by_user_id
                        WHERE id=:id
                        """
                    ),
                    {"checked_at": current, "checked_by_user_id": user_id, "id": int(item_id)},
                )
            else:
                res = db.execute(
                    text(
                        """
                        UPDATE remember_to_order_items
                        SET checked_at=NULL, checked_by_user_id=NULL
                        WHERE id=:id
                        """
                    ),
                    {"id": int(item_id)},
                )
            db.commit()
            return bool(res.rowcount)
        finally:
            db.close()


def _parse_dt(value) -> datetime | None:
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


__all__ = ["RememberToOrderItem", "RememberToOrderRepo"]
