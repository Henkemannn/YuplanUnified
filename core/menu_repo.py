from __future__ import annotations

from typing import Dict, Any

from sqlalchemy import text

from .db import get_session


class MenuRepo:
    """Minimal menu storage for weekview (SQLite-first for tests).

        Schema:
            weekview_menus(site_id TEXT, year INTEGER, week INTEGER, day INTEGER 1..7, meal TEXT 'lunch'|'dinner',
            alt1_text TEXT NULL, alt2_text TEXT NULL, dessert TEXT NULL,
                        UNIQUE(site_id, year, week, day, meal))
    """

    def _ensure_schema(self) -> None:
        db = get_session()
        try:
            dialect = db.bind.dialect.name if db.bind is not None else ""
            if dialect != "sqlite":
                return
            db.execute(text(
                """
                CREATE TABLE IF NOT EXISTS weekview_menus (
                    site_id TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    day INTEGER NOT NULL,
                    meal TEXT NOT NULL,
                    alt1_text TEXT NULL,
                    alt2_text TEXT NULL,
                    dessert TEXT NULL,
                    UNIQUE(site_id, year, week, day, meal)
                )
                """
            ))
            # Ensure required columns exist; if schema mismatch (older ad-hoc table), recreate
            cols = {row[1] for row in db.execute(text("PRAGMA table_info('weekview_menus')")).fetchall()}
            required = {"site_id", "year", "week", "day", "meal", "alt1_text", "alt2_text", "dessert"}
            if not required.issubset(cols):
                db.execute(text("DROP TABLE IF EXISTS weekview_menus"))
                db.execute(text(
                    """
                    CREATE TABLE weekview_menus (
                        site_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        day INTEGER NOT NULL,
                        meal TEXT NOT NULL,
                        alt1_text TEXT NULL,
                        alt2_text TEXT NULL,
                        dessert TEXT NULL,
                        UNIQUE(site_id, year, week, day, meal)
                    )
                    """
                ))
            db.commit()
        finally:
            db.close()

    def upsert_menu_item(
        self,
        site_id: str,
        year: int,
        week: int,
        day: int,
        meal: str,
        alt1_text: str | None,
        alt2_text: str | None,
        dessert: str | None,
    ) -> None:
        self._ensure_schema()
        db = get_session()
        try:
            db.execute(
                text(
                    """
                    INSERT INTO weekview_menus(site_id, year, week, day, meal, alt1_text, alt2_text, dessert)
                    VALUES(:s, :y, :w, :d, :m, :a1, :a2, :ds)
                    ON CONFLICT(site_id, year, week, day, meal)
                    DO UPDATE SET alt1_text=excluded.alt1_text, alt2_text=excluded.alt2_text, dessert=excluded.dessert
                    """
                ),
                {"s": site_id, "y": year, "w": week, "d": day, "m": meal, "a1": alt1_text, "a2": alt2_text, "ds": dessert},
            )
            db.commit()
        finally:
            db.close()

    def get_menu_day(self, site_id: str, year: int, week: int, day: int) -> Dict[str, Any]:
        self._ensure_schema()
        db = get_session()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT meal, alt1_text, alt2_text, dessert
                    FROM weekview_menus
                    WHERE site_id=:s AND year=:y AND week=:w AND day=:d
                    """
                ),
                {"s": site_id, "y": year, "w": week, "d": day},
            ).fetchall()
            # Stable shape with empty-string defaults
            out: Dict[str, Any] = {
                "lunch": {"alt1_text": "", "alt2_text": "", "dessert": ""},
                "dinner": {"alt1_text": "", "alt2_text": "", "dessert": ""},
            }
            for r in rows:
                meal = str(r[0])
                alt1 = r[1] if r[1] is not None else ""
                alt2 = r[2] if r[2] is not None else ""
                dessert = r[3] if r[3] is not None else ""
                if meal == "lunch":
                    out["lunch"]["alt1_text"] = alt1
                    out["lunch"]["alt2_text"] = alt2
                    out["lunch"]["dessert"] = dessert
                elif meal == "dinner":
                    out["dinner"]["alt1_text"] = alt1
                    out["dinner"]["alt2_text"] = alt2
                    out["dinner"]["dessert"] = dessert
            return out
        finally:
            db.close()

    def get_menu_week(self, site_id: str, year: int, week: int) -> Dict[str, Any]:
        self._ensure_schema()
        db = get_session()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT day, meal, alt1_text, alt2_text, dessert
                    FROM weekview_menus
                    WHERE site_id=:s AND year=:y AND week=:w
                    ORDER BY day, meal
                    """
                ),
                {"s": site_id, "y": year, "w": week},
            ).fetchall()
            day_map = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}
            out: Dict[str, Any] = {"days": {}}
            for i in range(1, 8):
                out["days"][day_map[i]] = {}
            for r in rows:
                day = int(r[0])
                meal = str(r[1])
                alt1 = r[2]
                alt2 = r[3]
                dessert = r[4]
                dm = out["days"][day_map.get(day, "mon")]
                if meal == "lunch":
                    obj: Dict[str, Any] = {}
                    if alt1 is not None:
                        obj["alt1"] = alt1
                    if alt2 is not None:
                        obj["alt2"] = alt2
                    if dessert is not None:
                        obj["dessert"] = dessert
                    if obj:
                        dm["lunch"] = obj
                elif meal == "dinner":
                    obj = {}
                    if alt1 is not None:
                        obj["alt1"] = alt1
                    if alt2 is not None:
                        obj["alt2"] = alt2
                    if obj:
                        dm["dinner"] = obj
            return out
        finally:
            db.close()
