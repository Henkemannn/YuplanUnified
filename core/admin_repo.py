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
                            tenant_id INTEGER NULL,
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
                            tenant_id INTEGER NULL,
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

    def list_sites_for_tenant(self, tenant_id: int | str) -> list[dict]:
        """List sites for a given tenant when schema supports it.

        If the sites table lacks a tenant_id column (sqlite dev fallback), returns an empty list
        to avoid leaking cross-tenant data. Superuser flows should call list_sites().
        """
        db = get_session()
        try:
            # Ensure table exists on sqlite
            if _is_sqlite(db):
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS sites (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            tenant_id INTEGER NULL,
                            version INTEGER NOT NULL DEFAULT 0,
                            notes TEXT NULL,
                            updated_at TEXT
                        )
                        """
                    )
                )
            # Detect presence of tenant_id column
            has_col = False
            try:
                cols = db.execute(text("PRAGMA table_info('sites')")).fetchall()
                has_col = any(str(c[1]) == "tenant_id" for c in cols)
            except Exception:
                # Postgres path
                try:
                    chk = db.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='sites' AND column_name='tenant_id'"))
                    has_col = chk.fetchone() is not None
                except Exception:
                    has_col = False
            if not has_col:
                return []
            rows = db.execute(
                text("SELECT id, name, COALESCE(version,0) FROM sites WHERE tenant_id=:t ORDER BY name"),
                {"t": int(tenant_id) if str(tenant_id).isdigit() else tenant_id},
            ).fetchall()
            return [{"id": r[0], "name": r[1], "version": int(r[2] or 0)} for r in rows]
        finally:
            db.close()


class DepartmentsRepo:
    def create_department(
        self,
        site_id: str,
        name: str,
        resident_count_mode: str,
        resident_count_fixed: int | None,
        notes: str | None = None,
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
                if notes is not None and str(notes).strip() != "":
                    db.execute(
                        text(
                            """
                            INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version)
                            VALUES(:id, :site_id, :name, :mode, :fixed, :notes, 0)
                            """
                        ),
                        {"id": did, "site_id": site_id, "name": name, "mode": resident_count_mode, "fixed": rc_fixed, "notes": str(notes).strip()},
                    )
                else:
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
                # Detect optional notes column in non-sqlite and include when present
                has_notes = False
                try:
                    chk = db.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='departments' AND column_name='notes'"))
                    has_notes = chk.fetchone() is not None
                except Exception:
                    has_notes = False
                if has_notes and notes is not None and str(notes).strip() != "":
                    db.execute(
                        text(
                            """
                            INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes)
                            VALUES(:id, :site_id, :name, :mode, :fixed, :notes)
                            """
                        ),
                        {"id": did, "site_id": site_id, "name": name, "mode": resident_count_mode, "fixed": rc_fixed, "notes": str(notes).strip()},
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
            return {"id": did, "site_id": site_id, "name": name, "resident_count_mode": resident_count_mode, "resident_count_fixed": rc_fixed, "notes": (str(notes).strip() if notes else "")}, 0
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
                            -- Optional Phase 3 flag: count as done (debiterbar) always
                            always_mark INTEGER NOT NULL DEFAULT 0,
                            PRIMARY KEY (department_id, diet_type_id)
                        )
                        """
                    )
                )
            # Detect optional column presence
            cols = {c[1] for c in db.execute(text("PRAGMA table_info('department_diet_defaults')")).fetchall()}
            if "always_mark" in cols:
                rows = db.execute(
                    text(
                        """
                        SELECT diet_type_id, default_count, always_mark
                        FROM department_diet_defaults
                        WHERE department_id=:d
                        ORDER BY diet_type_id
                        """
                    ),
                    {"d": dept_id},
                ).fetchall()
                return [
                    {
                        "diet_type_id": r[0],
                        "default_count": int(r[1]),
                        "always_mark": bool(r[2] or 0),
                    }
                    for r in rows
                ]
            else:
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
                return [{"diet_type_id": r[0], "default_count": int(r[1]), "always_mark": False} for r in rows]
        finally:
            db.close()


class DietTypesRepo:
    """Repository for managing dietary types (specialkost), now scoped per site."""

    def _ensure_table(self, db) -> None:
        if _is_sqlite(db):
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS dietary_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        -- tenant_id kept for backward-compat in some environments
                        tenant_id INTEGER NULL,
                        site_id TEXT NULL,
                        name TEXT NOT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            # Add missing site_id column for older dev DBs; keep it NULL-able to avoid breaking existing rows
            try:
                cols = {r[1] for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
                if "site_id" not in cols:
                    db.execute(text("ALTER TABLE dietary_types ADD COLUMN site_id TEXT"))
            except Exception:
                pass
            # Helpful index for lookups
            try:
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_dietary_types_site_name ON dietary_types(site_id, name)"))
            except Exception:
                pass

    def list_all(self, site_id: str) -> list[dict]:
        """List all dietary types for a given site."""
        db = get_session()
        try:
            self._ensure_table(db)
            # If site_id column exists, filter by it; else return empty list to encourage DB reset
            try:
                cols = {r[1] for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
                if "site_id" not in cols:
                    # Schema missing site_id: return empty to force isolation (devs should reset DB)
                    rows = []
                else:
                    if not site_id:
                        # Strict isolation: require site_id; routes should redirect to select-site
                        rows = []
                    else:
                        rows = db.execute(
                            text("SELECT id, name, default_select FROM dietary_types WHERE site_id=:s ORDER BY name"),
                            {"s": site_id},
                        ).fetchall()
            except Exception:
                rows = []
            return [
                {"id": int(r[0]), "name": str(r[1]), "default_select": bool(r[2])}
                for r in rows
            ]
        finally:
            db.close()

    def get_by_id(self, diet_type_id: int) -> dict | None:
        """Get a single dietary type by ID."""
        db = get_session()
        try:
            self._ensure_table(db)
            row = db.execute(
                text("SELECT id, site_id, name, default_select FROM dietary_types WHERE id=:id"),
                {"id": diet_type_id},
            ).fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "site_id": (str(row[1]) if row[1] is not None else None),
                "name": str(row[2]),
                "default_select": bool(row[3]),
            }
        finally:
            db.close()

    def create(self, *args, **kwargs) -> int:
        """Create a new dietary type. Accepts both legacy and site-scoped signatures.

        Supported usages:
        - create(name="Glutenfri", default_select=False, site_id="s1")
        - create(site_id="s1", name="Glutenfri", default_select=False)
        - create(tenant_id=1, name="Glutenfri", default_select=False)  # legacy
        """
        # Normalize arguments
        site_id = kwargs.get("site_id")
        tenant_id = kwargs.get("tenant_id")
        name = kwargs.get("name")
        default_select = bool(kwargs.get("default_select", False))
        # Allow positional pattern (site_id, name, default_select)
        if not name and len(args) >= 2 and isinstance(args[1], str):
            # Either (site_id, name, default_select) or (name, default_select)
            if len(args) >= 3 and isinstance(args[2], (bool, int)):
                # Assume (site_id, name, default_select)
                site_id = args[0]
                name = args[1]
                default_select = bool(args[2])
            else:
                # (name, default_select)
                name = args[0]
                default_select = bool(args[1]) if len(args) >= 2 else False
        elif not name and len(args) >= 1 and isinstance(args[0], str):
            name = args[0]
            default_select = bool(args[1]) if len(args) >= 2 else default_select
        if not name:
            raise ValueError("name is required")
        db = get_session()
        try:
            self._ensure_table(db)
            if _is_sqlite(db):
                cols = {r[1] for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
                if "tenant_id" in cols:
                    # If legacy NOT NULL constraint exists, provide a default value (1)
                    notnull_map = {str(r[1]): int(r[3] or 0) for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
                    needs_tenant = bool(notnull_map.get("tenant_id", 0))
                    if needs_tenant:
                        tval = int(tenant_id) if tenant_id is not None else 1
                        db.execute(
                            text("INSERT INTO dietary_types(tenant_id, site_id, name, default_select) VALUES(:t, :s, :n, :d)"),
                            {"t": tval, "s": site_id, "n": name, "d": 1 if default_select else 0},
                        )
                    else:
                        db.execute(
                            text("INSERT INTO dietary_types(site_id, name, default_select) VALUES(:s, :n, :d)"),
                            {"s": site_id, "n": name, "d": 1 if default_select else 0},
                        )
                else:
                    db.execute(
                        text("INSERT INTO dietary_types(site_id, name, default_select) VALUES(:s, :n, :d)"),
                        {"s": site_id, "n": name, "d": 1 if default_select else 0},
                    )
                row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
                new_id = int(row[0]) if row else 0
            else:
                if tenant_id is not None:
                    res = db.execute(
                        text("INSERT INTO dietary_types(tenant_id, site_id, name, default_select) VALUES(:t, :s, :n, :d) RETURNING id"),
                        {"t": int(tenant_id), "s": site_id, "n": name, "d": default_select},
                    )
                else:
                    res = db.execute(
                        text("INSERT INTO dietary_types(site_id, name, default_select) VALUES(:s, :n, :d) RETURNING id"),
                        {"s": site_id, "n": name, "d": default_select},
                    )
                row = res.fetchone()
                new_id = int(row[0]) if row else 0
            db.commit()
            return new_id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update(self, diet_type_id: int, name: str | None = None, default_select: bool | None = None) -> None:
        """Update dietary type name and/or default_select. TODO: Add ETag concurrency."""
        db = get_session()
        try:
            sets = []
            params: dict = {"id": diet_type_id}
            if name is not None:
                sets.append("name=:name")
                params["name"] = name
            if default_select is not None:
                sets.append("default_select=:ds")
                params["ds"] = 1 if default_select else 0
            if not sets:
                return
            sql = f"UPDATE dietary_types SET {', '.join(sets)} WHERE id=:id"
            db.execute(text(sql), params)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete(self, diet_type_id: int) -> None:
        """Delete a dietary type by ID."""
        db = get_session()
        try:
            db.execute(text("DELETE FROM dietary_types WHERE id=:id"), {"id": diet_type_id})
            db.commit()
        except Exception:
            db.rollback()
            raise
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
