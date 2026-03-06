from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from .db import get_session


@dataclass
class PrepNoteItem:
    id: int
    site_id: str
    user_id: int | None
    text: str
    created_at: datetime | None
    is_active: bool


class PrepNotesRepo:
    def _ensure_schema(self, db) -> None:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS prep_notes (
                    id INTEGER PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    user_id INTEGER NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_prep_notes_site_user_active_created
                ON prep_notes(site_id, user_id, is_active, created_at)
                """
            )
        )

    def list_active_for_user(self, site_id: str, user_id: int | None, limit: int = 20) -> list[PrepNoteItem]:
        if not site_id:
            return []
        db = get_session()
        try:
            self._ensure_schema(db)
            if user_id is None:
                rows = db.execute(
                    text(
                        """
                        SELECT id, site_id, user_id, text, created_at, is_active
                        FROM prep_notes
                        WHERE site_id=:sid
                          AND user_id IS NULL
                          AND is_active=1
                        ORDER BY created_at DESC, id DESC
                        LIMIT :lim
                        """
                    ),
                    {"sid": site_id, "lim": int(limit)},
                ).fetchall()
            else:
                rows = db.execute(
                    text(
                        """
                        SELECT id, site_id, user_id, text, created_at, is_active
                        FROM prep_notes
                        WHERE site_id=:sid
                          AND user_id=:uid
                          AND is_active=1
                        ORDER BY created_at DESC, id DESC
                        LIMIT :lim
                        """
                    ),
                    {"sid": site_id, "uid": int(user_id), "lim": int(limit)},
                ).fetchall()
        finally:
            db.close()
        return [_row_to_item(r) for r in rows]

    def add(self, site_id: str, user_id: int | None, text_val: str) -> int:
        if not site_id:
            raise ValueError("site_id is required")
        if not text_val:
            raise ValueError("text is required")

        db = get_session()
        try:
            self._ensure_schema(db)
            params = {
                "sid": site_id,
                "uid": int(user_id) if user_id is not None else None,
                "txt": text_val,
            }
            dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
            if dialect == "postgresql":
                res = db.execute(
                    text(
                        """
                        INSERT INTO prep_notes (site_id, user_id, text)
                        VALUES (:sid, :uid, :txt)
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
                        INSERT INTO prep_notes (site_id, user_id, text)
                        VALUES (:sid, :uid, :txt)
                        """
                    ),
                    params,
                )
                item_id = int(res.lastrowid or 0)
            db.commit()
            return item_id
        finally:
            db.close()

    def deactivate(self, note_id: int, site_id: str, user_id: int | None) -> bool:
        if not site_id:
            return False
        db = get_session()
        try:
            self._ensure_schema(db)
            if user_id is None:
                res = db.execute(
                    text(
                        """
                        UPDATE prep_notes
                        SET is_active=0
                        WHERE id=:id AND site_id=:sid AND user_id IS NULL
                        """
                    ),
                    {"id": int(note_id), "sid": site_id},
                )
            else:
                res = db.execute(
                    text(
                        """
                        UPDATE prep_notes
                        SET is_active=0
                        WHERE id=:id AND site_id=:sid AND user_id=:uid
                        """
                    ),
                    {"id": int(note_id), "sid": site_id, "uid": int(user_id)},
                )
            db.commit()
            return bool(res.rowcount)
        finally:
            db.close()


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


def _row_to_item(row) -> PrepNoteItem:
    return PrepNoteItem(
        id=int(row[0]),
        site_id=str(row[1]),
        user_id=int(row[2]) if row[2] is not None else None,
        text=str(row[3] or ""),
        created_at=_parse_datetime(row[4]),
        is_active=bool(row[5]),
    )


__all__ = ["PrepNoteItem", "PrepNotesRepo"]
