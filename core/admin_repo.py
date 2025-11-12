from __future__ import annotations

import uuid
from typing import Iterable

from sqlalchemy import text

from .db import get_session
from .etag import ConcurrencyError


def _is_sqlite(db) -> bool:
    try:
        return (db.bind and db.bind.dialect and db.bind.dialect.name == "sqlite")
    except Exception:
        return True


class SitesRepo:
    def create_site(self, name: str) -> tuple[dict, int]:
        db = get_session()
        try:
            sid = str(uuid.uuid4())
            if _is_sqlite(db):
                # Ensure minimal admin tables exist for sqlite test/dev environments
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS sites (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            version INTEGER NOT NULL DEFAULT 0,
                            notes TEXT NULL,
                            updated_at TEXT
                        )
                        """
                    )
                )
                db.execute(
                    text(
                        """
                        INSERT INTO sites(id, name, version)
                        VALUES(:id, :name, 0)
                        """
                    ),
                    {"id": sid, "name": name},
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO sites(id, name)
                        VALUES(:id, :name)
                        """
                    ),
                    {"id": sid, "name": name},
                )
            db.commit()
            return {"id": sid, "name": name}, 0
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_sites(self) -> list[dict]:
        """List all sites (id, name, version)."""
        db = get_session()
        try:
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS sites (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            version INTEGER NOT NULL DEFAULT 0,
                            notes TEXT NULL,
                            updated_at TEXT
                        )
                        """
                    )
                )
            rows = db.execute(text("SELECT id, name, COALESCE(version,0) FROM sites ORDER BY name"))
            return [{"id": r[0], "name": r[1], "version": int(r[2] or 0)} for r in rows.fetchall()]
        finally:
            db.close()


class DepartmentsRepo:
    def create_department(
        self,
        site_id: str,
        name: str,
        resident_count_mode: str,
        resident_count_fixed: int | None,
    ) -> tuple[dict, int]:
        db = get_session()
        try:
            did = str(uuid.uuid4())
            rc_fixed = int(resident_count_fixed or 0)
            if _is_sqlite(db):
                # Ensure departments table exists (sqlite test/dev)
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS departments (
                            id TEXT PRIMARY KEY,
                            site_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            resident_count_mode TEXT NOT NULL,
                            resident_count_fixed INTEGER NOT NULL DEFAULT 0,
                            notes TEXT NULL,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT
                        )
                        """
                    )
                )
                db.execute(
                    text(
                        """
                        INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version)
                        VALUES(:id, :site_id, :name, :mode, :fixed, 0)
                        """
                    ),
                    {"id": did, "site_id": site_id, "name": name, "mode": resident_count_mode, "fixed": rc_fixed},
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed)
                        VALUES(:id, :site_id, :name, :mode, :fixed)
                        """
                    ),
                    {"id": did, "site_id": site_id, "name": name, "mode": resident_count_mode, "fixed": rc_fixed},
                )
            db.commit()
            return {"id": did, "site_id": site_id, "name": name, "resident_count_mode": resident_count_mode, "resident_count_fixed": rc_fixed}, 0
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_department(self, dept_id: str, expected_version: int, **fields) -> int:
        db = get_session()
        try:
            sets = []
            params = {"id": dept_id, "v": int(expected_version)}
            if "name" in fields and fields["name"] is not None:
                sets.append("name=:name")
                params["name"] = str(fields["name"]).strip()
            if "resident_count_mode" in fields and fields["resident_count_mode"] is not None:
                sets.append("resident_count_mode=:mode")
                params["mode"] = str(fields["resident_count_mode"]).strip()
            if "resident_count_fixed" in fields and fields["resident_count_fixed"] is not None:
                sets.append("resident_count_fixed=:fixed")
                params["fixed"] = int(fields["resident_count_fixed"])
            if "notes" in fields and fields["notes"] is not None:
                sets.append("notes=:notes")
                params["notes"] = str(fields["notes"]).strip()
            if not sets:
                # No-op: still bump version to reflect write intent
                sets.append("version=version")  # sqlite path bumps separately; postgres will still increment
            if _is_sqlite(db):
                sql = f"UPDATE departments SET {', '.join(sets)}, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=:id AND version=:v"
            else:
                # Always bump version for postgres as part of update to maintain optimistic concurrency & collection ETag semantics.
                sql = f"UPDATE departments SET {', '.join(sets)}, version=version+1, updated_at=now() WHERE id=:id AND version=:v RETURNING version"
            res = db.execute(text(sql), params)
            if _is_sqlite(db):
                if res.rowcount == 0:
                    db.rollback()
                    raise ConcurrencyError("stale version")
                # fetch new version
                row = db.execute(text("SELECT version FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
                db.commit()
                return int(row[0]) if row else 0
            else:
                row = res.fetchone()
                if not row:
                    db.rollback()
                    raise ConcurrencyError("stale version")
                db.commit()
                return int(row[0])
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_department_notes(self, dept_id: str, expected_version: int, notes: str | None) -> int:
        return self.update_department(dept_id, expected_version, notes=notes)

    def get_version(self, dept_id: str) -> int | None:
        db = get_session()
        try:
            row = db.execute(text("SELECT version FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
            return int(row[0]) if row else None
        finally:
            db.close()

    def list_for_site(self, site_id: str) -> list[dict]:
        """List departments for a given site."""
        db = get_session()
        try:
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS departments (
                            id TEXT PRIMARY KEY,
                            site_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            resident_count_mode TEXT NOT NULL,
                            resident_count_fixed INTEGER NOT NULL DEFAULT 0,
                            notes TEXT NULL,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT
                        )
                        """
                    )
                )
            rows = db.execute(
                text(
                    """
                    SELECT id, site_id, name, resident_count_mode, resident_count_fixed, COALESCE(version,0)
                    FROM departments WHERE site_id=:s ORDER BY name
                    """
                ),
                {"s": site_id},
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "site_id": r[1],
                    "name": r[2],
                    "resident_count_mode": r[3],
                    "resident_count_fixed": int(r[4] or 0),
                    "version": int(r[5] or 0),
                }
                for r in rows
            ]
        finally:
            db.close()

    def upsert_department_diet_defaults(
        self, dept_id: str, expected_version: int, items: Iterable[dict]
    ) -> int:
        db = get_session()
        try:
            if expected_version is None:
                raise ConcurrencyError("missing version")
            # ensure department exists & optimistic concurrency check by bumping version at the end
            # SQLite test/dev fallback: ensure table exists (mirrors create_all bootstrap semantics)
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS department_diet_defaults (
                            department_id TEXT NOT NULL,
                            diet_type_id TEXT NOT NULL,
                            default_count INTEGER NOT NULL DEFAULT 0,
                            PRIMARY KEY (department_id, diet_type_id)
                        )
                        """
                    )
                )
            for it in items:
                diet_type_id = str(it["diet_type_id"]).strip()
                default_count = int(it["default_count"])
                if _is_sqlite(db):
                    db.execute(
                        text(
                            """
                            INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count)
                            VALUES(:d, :t, :c)
                            ON CONFLICT(department_id, diet_type_id)
                            DO UPDATE SET default_count=excluded.default_count
                            """
                        ),
                        {"d": dept_id, "t": diet_type_id, "c": default_count},
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count)
                            VALUES(:d, :t, :c)
                            ON CONFLICT(department_id, diet_type_id)
                            DO UPDATE SET default_count=excluded.default_count, updated_at=now()
                            """
                        ),
                        {"d": dept_id, "t": diet_type_id, "c": default_count},
                    )
            # bump owning department using optimistic concurrency
            if _is_sqlite(db):
                res = db.execute(
                    text(
                        """
                        UPDATE departments SET version=version+1, updated_at=CURRENT_TIMESTAMP
                        WHERE id=:id AND version=:v
                        """
                    ),
                    {"id": dept_id, "v": int(expected_version)},
                )
                if res.rowcount == 0:
                    db.rollback()
                    raise ConcurrencyError("stale version")
                row = db.execute(text("SELECT version FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
                db.commit()
                return int(row[0]) if row else 0
            else:
                row = db.execute(
                    text(
                        """
                        UPDATE departments SET version=version+1, updated_at=now()
                        WHERE id=:id AND version=:v
                        RETURNING version
                        """
                    ),
                    {"id": dept_id, "v": int(expected_version)},
                ).fetchone()
                if not row:
                    db.rollback()
                    raise ConcurrencyError("stale version")
                db.commit()
                return int(row[0])
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class NotesRepo:
    """Generic notes version bump helper (if needed in future)."""

    def touch(self, note_id: int, expected_version: int | None = None) -> None:
        db = get_session()
        try:
            if expected_version is None:
                db.execute(text("UPDATE notes SET updated_at=CURRENT_TIMESTAMP" if _is_sqlite(db) else "UPDATE notes SET updated_at=now()"))
            else:
                res = db.execute(
                    text(
                        "UPDATE notes SET version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=:id AND version=:v"
                        if _is_sqlite(db)
                        else "UPDATE notes SET updated_at=now() WHERE id=:id AND version=:v RETURNING id"
                    ),
                    {"id": note_id, "v": int(expected_version)},
                )
                if not _is_sqlite(db) and not res.fetchone():
                    raise ConcurrencyError("stale version")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class DietDefaultsRepo:
    def list_for_department(self, dept_id: str) -> list[dict]:
        db = get_session()
        try:
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS department_diet_defaults (
                            department_id TEXT NOT NULL,
                            diet_type_id TEXT NOT NULL,
                            default_count INTEGER NOT NULL DEFAULT 0,
                            PRIMARY KEY (department_id, diet_type_id)
                        )
                        """
                    )
                )
            rows = db.execute(
                text(
                    """
                    SELECT diet_type_id, default_count
                    FROM department_diet_defaults
                    WHERE department_id=:d
                    ORDER BY diet_type_id
                    """
                ),
                {"d": dept_id},
            ).fetchall()
            return [{"diet_type_id": r[0], "default_count": int(r[1])} for r in rows]
        finally:
            db.close()


class Alt2Repo:
    def bulk_upsert(self, flags: Iterable[dict]) -> list[dict]:
        """Idempotent bulk upsert for alt2 flags.

        Each item: {site_id, department_id, week, weekday, enabled}
        Returns list with versions: [{..., version:int}]
        """
        db = get_session()
        try:
            dialect = db.bind.dialect.name if db.bind is not None else ""
            out: list[dict] = []
            for it in flags:
                params = {
                    "site_id": str(it["site_id"]),
                    "department_id": str(it["department_id"]),
                    "week": int(it["week"]),
                    "weekday": int(it["weekday"]),
                    "enabled": bool(it["enabled"]),
                }
                if dialect == "sqlite":
                    # Ensure table exists
                    db.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS alt2_flags (
                                site_id TEXT NOT NULL,
                                department_id TEXT NOT NULL,
                                week INTEGER NOT NULL,
                                weekday INTEGER NOT NULL,
                                enabled BOOLEAN NOT NULL DEFAULT 0,
                                version INTEGER NOT NULL DEFAULT 0,
                                updated_at TEXT,
                                PRIMARY KEY (site_id, department_id, week, weekday)
                            )
                            """
                        )
                    )
                    # Do not update if no change (preserve version)
                    db.execute(
                        text(
                            """
                            INSERT INTO alt2_flags(site_id, department_id, week, weekday, enabled)
                            VALUES(:site_id, :department_id, :week, :weekday, :enabled)
                            ON CONFLICT(site_id, department_id, week, weekday)
                            DO UPDATE SET enabled=excluded.enabled, version=alt2_flags.version+1, updated_at=CURRENT_TIMESTAMP
                            WHERE alt2_flags.enabled IS DISTINCT FROM excluded.enabled
                            """
                        ),
                        params,
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO alt2_flags(site_id, department_id, week, weekday, enabled)
                            VALUES(:site_id, :department_id, :week, :weekday, :enabled)
                            ON CONFLICT(site_id, department_id, week, weekday)
                            DO UPDATE SET enabled=EXCLUDED.enabled, version=alt2_flags.version+1, updated_at=now()
                            WHERE alt2_flags.enabled IS DISTINCT FROM EXCLUDED.enabled
                            """
                        ),
                        params,
                    )
            db.commit()
            # Read back versions
            for it in flags:
                row = db.execute(
                    text(
                        """
                        SELECT version, enabled FROM alt2_flags
                        WHERE site_id=:site_id AND department_id=:department_id AND week=:week AND weekday=:weekday
                        """
                    ),
                    {
                        "site_id": str(it["site_id"]),
                        "department_id": str(it["department_id"]),
                        "week": int(it["week"]),
                        "weekday": int(it["weekday"]),
                    },
                ).fetchone()
                out.append({**it, "enabled": bool(row[1]) if row else bool(it["enabled"]), "version": int(row[0]) if row else 0})
            return out
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def collection_version(self, week: int, site_id: str | None = None) -> int:
        db = get_session()
        try:
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS alt2_flags (
                            site_id TEXT NOT NULL,
                            department_id TEXT NOT NULL,
                            week INTEGER NOT NULL,
                            weekday INTEGER NOT NULL,
                            enabled BOOLEAN NOT NULL DEFAULT 0,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT,
                            PRIMARY KEY (site_id, department_id, week, weekday)
                        )
                        """
                    )
                )
            if site_id:
                row = db.execute(
                    text(
                        "SELECT COALESCE(MAX(version),0) FROM alt2_flags WHERE site_id=:s AND week=:w"
                    ),
                    {"s": str(site_id), "w": int(week)},
                ).fetchone()
            else:
                row = db.execute(
                    text("SELECT COALESCE(MAX(version),0) FROM alt2_flags WHERE week=:w"),
                    {"w": int(week)},
                ).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        finally:
            db.close()

    def current_collection_version_or_none(self, week: int) -> int:
        return self.collection_version(week)

    def list_for_week(self, week: int) -> list[dict]:
        """List alt2 flags for a given week."""
        db = get_session()
        try:
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS alt2_flags (
                            site_id TEXT NOT NULL,
                            department_id TEXT NOT NULL,
                            week INTEGER NOT NULL,
                            weekday INTEGER NOT NULL,
                            enabled BOOLEAN NOT NULL DEFAULT 0,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT,
                            PRIMARY KEY (site_id, department_id, week, weekday)
                        )
                        """
                    )
                )
            rows = db.execute(
                text(
                    "SELECT site_id, department_id, week, weekday, enabled, COALESCE(version,0) FROM alt2_flags WHERE week=:w ORDER BY department_id, weekday"
                ),
                {"w": int(week)},
            ).fetchall()
            return [
                {
                    "site_id": r[0],
                    "department_id": r[1],
                    "week": int(r[2]),
                    "weekday": int(r[3]),
                    "enabled": bool(r[4]),
                    "version": int(r[5] or 0),
                }
                for r in rows
            ]
        finally:
            db.close()
    def department_version(self, week: int, department_id: str) -> int:
        """Return max version for a department's week flags (0 if none)."""
        db = get_session()
        try:
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS alt2_flags (
                            site_id TEXT NOT NULL,
                            department_id TEXT NOT NULL,
                            week INTEGER NOT NULL,
                            weekday INTEGER NOT NULL,
                            enabled BOOLEAN NOT NULL DEFAULT 0,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT,
                            PRIMARY KEY (site_id, department_id, week, weekday)
                        )
                        """
                    )
                )
            row = db.execute(
                text(
                    "SELECT COALESCE(MAX(version),0) FROM alt2_flags WHERE department_id=:d AND week=:w"
                ),
                {"d": str(department_id), "w": int(week)},
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        finally:
            db.close()

    def list_for_department_week(self, department_id: str, week: int) -> list[dict]:
        """List alt2 flags for a specific department and week."""
        db = get_session()
        try:
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS alt2_flags (
                            site_id TEXT NOT NULL,
                            department_id TEXT NOT NULL,
                            week INTEGER NOT NULL,
                            weekday INTEGER NOT NULL,
                            enabled BOOLEAN NOT NULL DEFAULT 0,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT,
                            PRIMARY KEY (site_id, department_id, week, weekday)
                        )
                        """
                    )
                )
            rows = db.execute(
                text(
                    "SELECT site_id, department_id, week, weekday, enabled, COALESCE(version,0) FROM alt2_flags WHERE department_id=:d AND week=:w ORDER BY weekday"
                ),
                {"d": str(department_id), "w": int(week)},
            ).fetchall()
            return [
                {
                    "site_id": r[0],
                    "department_id": r[1],
                    "week": int(r[2]),
                    "weekday": int(r[3]),
                    "enabled": bool(r[4]),
                    "version": int(r[5] or 0),
                }
                for r in rows
            ]
        finally:
            db.close()
