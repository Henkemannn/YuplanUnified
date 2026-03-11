from __future__ import annotations

from datetime import date as _date
from typing import Iterable

from sqlalchemy import text

from .db import get_session
from .week_key import build_week_key, normalize_week_key, parse_week_key, week_key_from_date


def _is_sqlite(db) -> bool:
    try:
        return (db.bind and db.bind.dialect and db.bind.dialect.name == "sqlite")
    except Exception:
        return True


def _ensure_menus_schema(db) -> None:
    if not _is_sqlite(db):
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS menus (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                week INTEGER NOT NULL,
                year INTEGER NOT NULL,
                status TEXT,
                updated_at TEXT
            )
            """
        )
    )


def _ensure_departments_schema(db) -> None:
    if not _is_sqlite(db):
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY,
                site_id TEXT,
                name TEXT
            )
            """
        )
    )


def _ensure_menu_choice_completion_schema(db) -> None:
    if not _is_sqlite(db):
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS menu_choice_completion (
                site_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                week_key TEXT NOT NULL,
                completed_at TEXT,
                UNIQUE (site_id, department_id, week_key)
            )
            """
        )
    )


def _menus_has_column(db, column_name: str) -> bool:
    try:
        cols = db.execute(text("PRAGMA table_info('menus')")).fetchall()
        return any(str(c[1]) == column_name for c in cols)
    except Exception:
        return False


def _sites_has_column(db, column_name: str) -> bool:
    try:
        cols = db.execute(text("PRAGMA table_info('sites')")).fetchall()
        return any(str(c[1]) == column_name for c in cols)
    except Exception:
        return False


def _resolve_tenant_id_for_site(db, site_id: str | None) -> int | None:
    if not site_id:
        return None
    if not _sites_has_column(db, "tenant_id"):
        return None
    row = db.execute(text("SELECT tenant_id FROM sites WHERE id=:id"), {"id": site_id}).fetchone()
    if not row or row[0] is None:
        return None
    try:
        return int(row[0])
    except Exception:
        return None


def get_published_weeks(site_id: str | None, from_week_key: str | None) -> list[str]:
    if not from_week_key:
        from_week_key = week_key_from_date(_date.today())
    from_year, from_week = parse_week_key(from_week_key)

    db = get_session()
    try:
        _ensure_menus_schema(db)
        params = {"from_year": from_year, "from_week": from_week}
        clauses = ["status = 'published'", "(year > :from_year OR (year = :from_year AND week >= :from_week))"]
        if _menus_has_column(db, "site_id") and site_id:
            # Include legacy menus without site_id for backward compatibility
            clauses.append("(site_id = :site_id OR site_id IS NULL)")
            params["site_id"] = site_id
        else:
            tenant_id = _resolve_tenant_id_for_site(db, site_id)
            if tenant_id is not None and _menus_has_column(db, "tenant_id"):
                clauses.append("tenant_id = :tenant_id")
                params["tenant_id"] = tenant_id
        sql = "SELECT year, week FROM menus WHERE " + " AND ".join(clauses) + " ORDER BY year, week"
        rows = db.execute(text(sql), params).fetchall()
        return [build_week_key(int(r[0]), int(r[1])) for r in rows]
    finally:
        db.close()


def get_required_weeks(site_id: str | None, from_week_key: str | None, n: int = 4) -> list[str]:
    published = get_published_weeks(site_id, from_week_key)
    if n <= 0:
        return []
    return published[:n]


def get_department_completion_status(site_id: str | None, week_keys: Iterable[str]) -> list[dict]:
    if not site_id:
        return []
    normalized = [normalize_week_key(wk) for wk in week_keys]
    db = get_session()
    try:
        _ensure_departments_schema(db)
        _ensure_menu_choice_completion_schema(db)
        dep_rows = db.execute(
            text(
                "SELECT id, name FROM departments "
                "WHERE site_id=:sid "
                "ORDER BY COALESCE(display_order, 2147483647), name"
            ),
            {"sid": site_id},
        ).fetchall()
        departments = [(str(r[0]), str(r[1] or "")) for r in dep_rows]

        completed: dict[str, set[str]] = {dep_id: set() for dep_id, _ in departments}
        if normalized:
            placeholders = ",".join([":wk" + str(i) for i in range(len(normalized))])
            params = {"sid": site_id}
            params.update({"wk" + str(i): wk for i, wk in enumerate(normalized)})
            rows = db.execute(
                text(
                    "SELECT department_id, week_key, completed_at "
                    "FROM menu_choice_completion "
                    f"WHERE site_id=:sid AND week_key IN ({placeholders})"
                ),
                params,
            ).fetchall()
            for r in rows:
                dep_id = str(r[0])
                wk = normalize_week_key(str(r[1]))
                completed_at = r[2]
                if completed_at:
                    completed.setdefault(dep_id, set()).add(wk)

        result = []
        for dep_id, dep_name in departments:
            missing = [wk for wk in normalized if wk not in completed.get(dep_id, set())]
            result.append(
                {
                    "department_id": dep_id,
                    "department_name": dep_name,
                    "missing_week_keys": missing,
                    "status": "needs_action" if missing else "ok",
                }
            )
        return result
    finally:
        db.close()


def get_menu_choice_overview(site_id: str | None, from_week_key: str | None, n: int = 4) -> dict:
    required_weeks = get_required_weeks(site_id, from_week_key, n=n)
    normalized = [normalize_week_key(wk) for wk in required_weeks]
    if not site_id or not normalized:
        return {"out_of_sync_count": 0, "department_gaps": []}

    db = get_session()
    try:
        _ensure_departments_schema(db)
        _ensure_menu_choice_completion_schema(db)
        dep_rows = db.execute(
            text(
                "SELECT id, name FROM departments "
                "WHERE site_id=:sid "
                "ORDER BY COALESCE(display_order, 2147483647), name"
            ),
            {"sid": site_id},
        ).fetchall()
        departments = [(str(r[0]), str(r[1] or "")) for r in dep_rows]

        completed_map: dict[str, set[str]] = {dep_id: set() for dep_id, _ in departments}
        started_map: dict[str, set[str]] = {dep_id: set() for dep_id, _ in departments}
        if normalized:
            placeholders = ",".join([":wk" + str(i) for i in range(len(normalized))])
            params = {"sid": site_id}
            params.update({"wk" + str(i): wk for i, wk in enumerate(normalized)})
            rows = db.execute(
                text(
                    "SELECT department_id, week_key, completed_at "
                    "FROM menu_choice_completion "
                    f"WHERE site_id=:sid AND week_key IN ({placeholders})"
                ),
                params,
            ).fetchall()
            for r in rows:
                dep_id = str(r[0])
                wk = normalize_week_key(str(r[1]))
                completed_at = r[2]
                if completed_at:
                    completed_map.setdefault(dep_id, set()).add(wk)
                else:
                    started_map.setdefault(dep_id, set()).add(wk)

        department_gaps = []
        for dep_id, dep_name in departments:
            completed_weeks = completed_map.get(dep_id, set())
            started_weeks = started_map.get(dep_id, set())
            seen_weeks = completed_weeks | started_weeks
            if not seen_weeks:
                department_gaps.append(
                    {
                        "name": dep_name,
                        "missing_weeks": [],
                        "status_text": "ej påbörjad",
                    }
                )
                continue
            if len(completed_weeks) < len(normalized):
                missing = [wk for wk in normalized if wk not in completed_weeks]
                week_numbers = [parse_week_key(wk)[1] for wk in missing]
                department_gaps.append(
                    {
                        "name": dep_name,
                        "missing_weeks": week_numbers,
                        "status_text": "påbörjad",
                    }
                )

        return {"out_of_sync_count": len(department_gaps), "department_gaps": department_gaps}
    finally:
        db.close()


__all__ = [
    "get_published_weeks",
    "get_required_weeks",
    "get_department_completion_status",
    "get_menu_choice_overview",
]
