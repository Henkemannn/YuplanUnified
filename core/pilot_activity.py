from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from .db import get_new_session


ALLOWED_EVENTS = {"login", "open_planera", "open_weekview", "open_admin"}


def _ensure_activity_table(db) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS pilot_activity_events (
                user_id INTEGER NULL,
                site_id VARCHAR(64) NULL,
                event_type VARCHAR(64) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    try:
        db.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_pilot_activity_site_created "
                "ON pilot_activity_events(site_id, created_at)"
            )
        )
    except Exception:
        pass


def track_activity(event_type: str, user_id: int | str | None, site_id: str | None) -> None:
    event = str(event_type or "").strip().lower()
    if event not in ALLOWED_EVENTS:
        return

    try:
        uid = int(user_id) if user_id is not None else None
    except Exception:
        uid = None

    sid = str(site_id or "").strip() or None

    db = get_new_session()
    try:
        _ensure_activity_table(db)
        db.execute(
            text(
                """
                INSERT INTO pilot_activity_events(user_id, site_id, event_type, created_at)
                VALUES(:user_id, :site_id, :event_type, CURRENT_TIMESTAMP)
                """
            ),
            {"user_id": uid, "site_id": sid, "event_type": event},
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _format_ts(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    raw = str(value).strip()
    if not raw:
        return ""
    return raw.replace("T", " ")[:16]


def get_latest_site_activity(limit: int = 300) -> list[dict[str, str]]:
    db = get_new_session()
    try:
        _ensure_activity_table(db)
        rows = db.execute(
            text(
                """
                SELECT
                    s.id AS site_id,
                    s.name AS site_name,
                    latest.user_id AS user_id,
                    latest.event_type AS event_type,
                    latest.created_at AS created_at,
                    u.full_name AS full_name,
                    u.email AS email,
                    u.username AS username
                FROM sites s
                LEFT JOIN (
                    SELECT site_id, user_id, event_type, created_at
                    FROM (
                        SELECT
                            site_id,
                            user_id,
                            event_type,
                            created_at,
                            ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY created_at DESC) AS rn
                        FROM pilot_activity_events
                        WHERE site_id IS NOT NULL AND site_id <> ''
                    ) ranked
                    WHERE ranked.rn = 1
                ) latest
                    ON latest.site_id = s.id
                LEFT JOIN users u
                    ON u.id = latest.user_id
                ORDER BY
                    CASE WHEN latest.created_at IS NULL THEN 1 ELSE 0 END,
                    latest.created_at DESC,
                    s.name ASC
                LIMIT :limit_rows
                """
            ),
            {"limit_rows": int(limit)},
        ).fetchall()

        out: list[dict[str, str]] = []
        for row in rows:
            full_name = str(row[5] or "").strip()
            email = str(row[6] or "").strip()
            username = str(row[7] or "").strip()
            uid = row[2]
            if full_name:
                user_label = full_name
            elif email:
                user_label = email
            elif username:
                user_label = username
            elif uid is not None:
                user_label = f"User #{uid}"
            else:
                user_label = ""

            out.append(
                {
                    "site_id": str(row[0] or ""),
                    "site_name": str(row[1] or ""),
                    "last_activity_time": _format_ts(row[4]),
                    "last_user": user_label,
                    "last_event": str(row[3] or ""),
                }
            )
        return out
    except Exception:
        return []
    finally:
        db.close()
