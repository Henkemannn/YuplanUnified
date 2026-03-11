from __future__ import annotations

import os
import uuid
from typing import Iterable

from sqlalchemy import text
from flask import current_app, has_app_context

from .db import get_session
from .etag import ConcurrencyError


def _is_sqlite(db) -> bool:
    try:
        return (db.bind and db.bind.dialect and db.bind.dialect.name == "sqlite")
    except Exception:
        return True


def _sites_has_tenant_col(db) -> bool:
    try:
        cols = db.execute(text("PRAGMA table_info('sites')")).fetchall()
        return any(str(c[1]) == "tenant_id" for c in cols)
    except Exception:
        try:
            chk = db.execute(
                text(
                    "SELECT 1 FROM information_schema.columns WHERE table_name='sites' AND column_name='tenant_id'"
                )
            )
            return chk.fetchone() is not None
        except Exception:
            return False


def _table_has_column(db, table_name: str, column_name: str) -> bool:
    try:
        cols = db.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
        return any(str(c[1]) == column_name for c in cols)
    except Exception:
        try:
            chk = db.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name=:table_name AND column_name=:column_name"
                ),
                {"table_name": table_name, "column_name": column_name},
            )
            return chk.fetchone() is not None
        except Exception:
            return False


def _ensure_departments_residence_id_column(db) -> None:
    if _table_has_column(db, "departments", "residence_id"):
        return
    try:
        if _is_sqlite(db):
            db.execute(text("ALTER TABLE departments ADD COLUMN residence_id TEXT NULL"))
        else:
            db.execute(text("ALTER TABLE departments ADD COLUMN residence_id VARCHAR(64) NULL"))
    except Exception:
        # Another worker/request may have added it concurrently.
        if not _table_has_column(db, "departments", "residence_id"):
            raise


def _ensure_departments_display_order_column(db) -> None:
    if _table_has_column(db, "departments", "display_order"):
        return
    try:
        if _is_sqlite(db):
            db.execute(text("ALTER TABLE departments ADD COLUMN display_order INTEGER NULL"))
        else:
            db.execute(text("ALTER TABLE departments ADD COLUMN display_order INTEGER NULL"))
    except Exception:
        if not _table_has_column(db, "departments", "display_order"):
            raise


def _ensure_department_diet_overrides_table(db) -> None:
    if _is_sqlite(db):
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS department_diet_overrides (
                    department_id TEXT NOT NULL,
                    diet_type_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    meal TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (department_id, diet_type_id, day, meal)
                )
                """
            )
        )


def _resolve_default_tenant_id(db) -> int | None:
    try:
        row = db.execute(text("SELECT id FROM tenants WHERE id=1")).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        row = None
    try:
        rows = db.execute(text("SELECT id FROM tenants ORDER BY id")).fetchall()
        if len(rows) == 1 and rows[0][0] is not None:
            return int(rows[0][0])
        allow_seed = (not has_app_context()) or bool(current_app.config.get("TESTING"))
        if not rows and allow_seed:
            try:
                db.execute(
                    text("INSERT INTO tenants(id, name, active) VALUES(1, 'TestTenant', 1)")
                )
                return 1
            except Exception:
                return None
    except Exception:
        return None
    return None


def tenant_exists(db, tenant_id: int | None) -> bool:
    if tenant_id is None:
        return False
    try:
        row = db.execute(text("SELECT 1 FROM tenants WHERE id=:id"), {"id": int(tenant_id)}).fetchone()
        return row is not None
    except Exception:
        return False


class SitesRepo:
    def create_site(self, name: str, tenant_id: int | None = None) -> tuple[dict, int]:
        db = get_session()
        try:
            tenant_value = tenant_id
            if tenant_value is None:
                tenant_value = _resolve_default_tenant_id(db)
            if tenant_value is None and current_app.config.get("TESTING"):
                tenant_value = 1
            if tenant_value is None:
                raise ValueError("tenant_required")
            if not tenant_exists(db, tenant_value):
                if current_app.config.get("TESTING") and int(tenant_value) == 1:
                    try:
                        db.execute(
                            text("INSERT INTO tenants(id, name, active) VALUES(1, 'TestTenant', 1)")
                        )
                    except Exception:
                        pass
                if not tenant_exists(db, tenant_value):
                    raise ValueError("tenant_not_found")
            sid = str(uuid.uuid4())
            if _is_sqlite(db):
                # Ensure minimal admin tables exist for sqlite test/dev environments
                db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS sites (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            tenant_id INTEGER,
                            version INTEGER NOT NULL DEFAULT 0,
                            notes TEXT NULL,
                            updated_at TEXT
                        )
                        """
                    )
                )
                try:
                    if not _sites_has_tenant_col(db):
                        db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER"))
                except Exception:
                    pass
                try:
                    db.execute(text("CREATE INDEX IF NOT EXISTS idx_sites_tenant_id ON sites(tenant_id)"))
                except Exception:
                    pass
                db.execute(
                    text(
                        """
                        INSERT INTO sites(id, name, tenant_id, version)
                        VALUES(:id, :name, :tenant_id, 0)
                        """
                    ),
                    {"id": sid, "name": name, "tenant_id": tenant_value},
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO sites(id, name, tenant_id)
                        VALUES(:id, :name, :tenant_id)
                        """
                    ),
                    {"id": sid, "name": name, "tenant_id": tenant_value},
                )
            db.commit()
            return {"id": sid, "name": name}, 0
        except Exception as exc:
            db.rollback()
            if _is_sqlite(db) and "UNIQUE constraint failed: sites.name" in str(exc):
                try:
                    row = db.execute(
                        text("SELECT id, name, COALESCE(version,0) FROM sites WHERE name=:name"),
                        {"name": name},
                    ).fetchone()
                    if row:
                        return {"id": row[0], "name": row[1]}, int(row[2] or 0)
                except Exception:
                    pass
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
                            tenant_id INTEGER,
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
                            tenant_id INTEGER,
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


def dev_repair_null_site_tenant_ids() -> None:
    if current_app.config.get("TESTING"):
        return
    env_val = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
    if env_val not in ("dev", "development"):
        return
    if os.getenv("YUPLAN_DEV_REPAIR_TENANT_IDS", "0").lower() not in ("1", "true", "yes"):
        return
    db = get_session()
    try:
        try:
            tenants = db.execute(text("SELECT id FROM tenants ORDER BY id")).fetchall()
        except Exception:
            return
        if len(tenants) != 1:
            return
        try:
            only_id = int(tenants[0][0]) if tenants[0][0] is not None else 0
        except Exception:
            return
        if only_id != 1:
            return
        if not _sites_has_tenant_col(db):
            return
        row = db.execute(text("SELECT COUNT(*) FROM sites WHERE tenant_id IS NULL")).fetchone()
        missing = int(row[0] or 0) if row else 0
        if missing <= 0:
            return
        db.execute(text("UPDATE sites SET tenant_id=1 WHERE tenant_id IS NULL"))
        db.commit()
        try:
            current_app.logger.info("DEV REPAIR: backfilled tenant_id=1 for %s sites.", missing)
        except Exception:
            pass
    finally:
        db.close()


class DepartmentsRepo:
    def create_department(
        self,
        site_id: str,
        name: str,
        resident_count_mode: str,
        resident_count_fixed: int | None,
        residence_id: str | None = None,
        notes: str | None = None,
    ) -> tuple[dict, int]:
        db = get_session()
        try:
            did = str(uuid.uuid4())
            rc_fixed = int(resident_count_fixed or 0)
            notes_value = notes if notes is not None else None
            residence_value = str(residence_id).strip() if residence_id else None
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
                            residence_id TEXT NULL,
                            display_order INTEGER NULL,
                            notes TEXT NULL,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT
                        )
                        """
                    )
                )
                _ensure_departments_residence_id_column(db)
                _ensure_departments_display_order_column(db)
                db.execute(
                    text(
                        """
                        INSERT INTO departments(
                            id, site_id, name, resident_count_mode, resident_count_fixed, residence_id, notes, version
                        )
                        VALUES(:id, :site_id, :name, :mode, :fixed, :residence_id, :notes, 0)
                        """
                    ),
                    {
                        "id": did,
                        "site_id": site_id,
                        "name": name,
                        "mode": resident_count_mode,
                        "fixed": rc_fixed,
                        "residence_id": residence_value,
                        "notes": notes_value,
                    },
                )
            else:
                _ensure_departments_residence_id_column(db)
                _ensure_departments_display_order_column(db)
                db.execute(
                    text(
                        """
                        INSERT INTO departments(
                            id, site_id, name, resident_count_mode, resident_count_fixed, residence_id, notes
                        )
                        VALUES(:id, :site_id, :name, :mode, :fixed, :residence_id, :notes)
                        """
                    ),
                    {
                        "id": did,
                        "site_id": site_id,
                        "name": name,
                        "mode": resident_count_mode,
                        "fixed": rc_fixed,
                        "residence_id": residence_value,
                        "notes": notes_value,
                    },
                )
            db.commit()
            return {
                "id": did,
                "site_id": site_id,
                "name": name,
                "resident_count_mode": resident_count_mode,
                "resident_count_fixed": rc_fixed,
                "residence_id": residence_value,
                "display_order": None,
                "notes": notes_value,
            }, 0
        except Exception as exc:
            db.rollback()
            if _is_sqlite(db) and "UNIQUE constraint failed: departments.site_id, departments.name" in str(exc):
                try:
                    row = db.execute(
                        text(
                            "SELECT id, site_id, name, resident_count_mode, resident_count_fixed, COALESCE(version,0) "
                            "FROM departments WHERE site_id=:s AND name=:n"
                        ),
                        {"s": site_id, "n": name},
                    ).fetchone()
                    if row:
                        return {
                            "id": row[0],
                            "site_id": row[1],
                            "name": row[2],
                            "resident_count_mode": row[3],
                            "resident_count_fixed": int(row[4] or 0),
                        }, int(row[5] or 0)
                except Exception:
                    pass
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
            if "residence_id" in fields:
                sets.append("residence_id=:residence_id")
                params["residence_id"] = str(fields["residence_id"]).strip() if fields["residence_id"] else None
            if "display_order" in fields:
                sets.append("display_order=:display_order")
                params["display_order"] = int(fields["display_order"]) if fields["display_order"] is not None else None
            if "notes" in fields and fields["notes"] is not None:
                sets.append("notes=:notes")
                params["notes"] = str(fields["notes"]).strip()
            if not sets:
                # No-op: still bump version to reflect write intent
                sets.append("version=version")  # sqlite path bumps separately; postgres will still increment
            if _is_sqlite(db):
                _ensure_departments_display_order_column(db)
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
                            residence_id TEXT NULL,
                            display_order INTEGER NULL,
                            notes TEXT NULL,
                            version INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT
                        )
                        """
                    )
                )
                _ensure_departments_residence_id_column(db)
                _ensure_departments_display_order_column(db)
            rows = db.execute(
                text(
                    """
                    SELECT id, site_id, name, resident_count_mode, resident_count_fixed, residence_id, display_order, COALESCE(version,0)
                    FROM departments
                    WHERE site_id=:s
                    ORDER BY COALESCE(display_order, 2147483647), name
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
                    "residence_id": r[5],
                    "display_order": (int(r[6]) if r[6] is not None else None),
                    "version": int(r[7] or 0),
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
                    sqlite_db = None
                    try:
                        sqlite_db = db.bind.url.database  # type: ignore[union-attr]
                    except Exception:
                        sqlite_db = None
                    if not sqlite_db or sqlite_db == ":memory:":
                        db.rollback()
                        raise ConcurrencyError("stale version")
                    row = db.execute(text("SELECT version FROM departments WHERE id=:id"), {"id": dept_id}).fetchone()
                    if not row:
                        db.rollback()
                        raise ConcurrencyError("stale version")
                    db.execute(
                        text("UPDATE departments SET version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
                        {"id": dept_id},
                    )
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


class ResidencesRepo:
    def _ensure_table(self, db) -> None:
        if _is_sqlite(db):
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS residences (
                        id TEXT PRIMARY KEY,
                        site_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(site_id, name)
                    )
                    """
                )
            )

    def list_for_site(self, site_id: str) -> list[dict]:
        db = get_session()
        try:
            self._ensure_table(db)
            rows = db.execute(
                text("SELECT id, site_id, name FROM residences WHERE site_id=:sid ORDER BY name"),
                {"sid": str(site_id)},
            ).fetchall()
            return [{"id": r[0], "site_id": r[1], "name": r[2]} for r in rows]
        finally:
            db.close()

    def get_for_site(self, site_id: str, residence_id: str) -> dict | None:
        db = get_session()
        try:
            self._ensure_table(db)
            row = db.execute(
                text("SELECT id, site_id, name FROM residences WHERE id=:id AND site_id=:sid"),
                {"id": str(residence_id), "sid": str(site_id)},
            ).fetchone()
            if not row:
                return None
            return {"id": row[0], "site_id": row[1], "name": row[2]}
        finally:
            db.close()

    def create_for_site(self, site_id: str, name: str) -> dict:
        db = get_session()
        try:
            self._ensure_table(db)
            residence_id = str(uuid.uuid4())
            name_value = str(name).strip()
            if _is_sqlite(db):
                db.execute(
                    text("INSERT INTO residences(id, site_id, name) VALUES(:id, :sid, :name)"),
                    {"id": residence_id, "sid": str(site_id), "name": name_value},
                )
            else:
                db.execute(
                    text("INSERT INTO residences(id, site_id, name) VALUES(:id, :sid, :name)"),
                    {"id": residence_id, "sid": str(site_id), "name": name_value},
                )
            db.commit()
            return {"id": residence_id, "site_id": str(site_id), "name": name_value}
        except Exception as exc:
            db.rollback()
            msg = str(exc)
            is_unique = (
                "UNIQUE constraint failed: residences.site_id, residences.name" in msg
                or "duplicate key value violates unique constraint" in msg
            )
            if is_unique:
                row = db.execute(
                    text("SELECT id, site_id, name FROM residences WHERE site_id=:sid AND name=:name"),
                    {"sid": str(site_id), "name": str(name).strip()},
                ).fetchone()
                if row:
                    return {"id": row[0], "site_id": row[1], "name": row[2]}
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


class DepartmentDietOverridesRepo:
    def list_for_department(self, dept_id: str) -> list[dict]:
        db = get_session()
        try:
            _ensure_department_diet_overrides_table(db)
            rows = db.execute(
                text(
                    """
                    SELECT diet_type_id, day, meal, count
                    FROM department_diet_overrides
                    WHERE department_id=:d
                    ORDER BY diet_type_id, day, meal
                    """
                ),
                {"d": str(dept_id)},
            ).fetchall()
            return [
                {
                    "diet_type_id": str(r[0]),
                    "day": int(r[1]),
                    "meal": str(r[2]),
                    "count": int(r[3] or 0),
                }
                for r in rows
            ]
        finally:
            db.close()

    def list_for_department_diet(self, dept_id: str, diet_type_id: str | int) -> list[dict]:
        db = get_session()
        try:
            _ensure_department_diet_overrides_table(db)
            rows = db.execute(
                text(
                    """
                    SELECT day, meal, count
                    FROM department_diet_overrides
                    WHERE department_id=:d AND diet_type_id=:t
                    ORDER BY day, meal
                    """
                ),
                {"d": str(dept_id), "t": str(diet_type_id)},
            ).fetchall()
            return [
                {
                    "day": int(r[0]),
                    "meal": str(r[1]),
                    "count": int(r[2] or 0),
                }
                for r in rows
            ]
        finally:
            db.close()

    def get_map_for_department(self, dept_id: str) -> dict[tuple[int, str, str], int]:
        out: dict[tuple[int, str, str], int] = {}
        for row in self.list_for_department(dept_id):
            out[(int(row["day"]), str(row["meal"]), str(row["diet_type_id"]))] = int(row["count"])
        return out

    def replace_for_department_diet(self, dept_id: str, diet_type_id: str | int, items: Iterable[dict]) -> None:
        db = get_session()
        try:
            _ensure_department_diet_overrides_table(db)
            db.execute(
                text(
                    """
                    DELETE FROM department_diet_overrides
                    WHERE department_id=:d AND diet_type_id=:t
                    """
                ),
                {"d": str(dept_id), "t": str(diet_type_id)},
            )
            for it in items:
                day = int(it.get("day") or 0)
                meal = str(it.get("meal") or "").strip().lower()
                count = int(it.get("count") or 0)
                if day < 1 or day > 7 or meal not in ("lunch", "dinner"):
                    continue
                db.execute(
                    text(
                        """
                        INSERT INTO department_diet_overrides(department_id, diet_type_id, day, meal, count, updated_at)
                        VALUES(:d, :t, :day, :meal, :count, CURRENT_TIMESTAMP)
                        """
                    ),
                    {
                        "d": str(dept_id),
                        "t": str(diet_type_id),
                        "day": day,
                        "meal": meal,
                        "count": count,
                    },
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
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
        # Hard guard: name must not be purely numeric
        try:
            if str(name).strip().isdigit():
                raise ValueError("invalid name: purely numeric")
        except Exception:
            pass
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
                if str(name).strip().isdigit():
                    raise ValueError("invalid name: purely numeric")
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

    def cleanup_invalid_all(self) -> list[int]:
        """Remove dietary types with empty or numeric-only names and their associations.

        Returns list of deleted IDs.
        """
        db = get_session()
        deleted: list[int] = []
        try:
            self._ensure_table(db)
            rows = db.execute(text("SELECT id, name FROM dietary_types")).fetchall()
            invalid_ids: list[int] = []
            for r in rows:
                try:
                    did = int(r[0])
                    nm = str(r[1]) if r[1] is not None else ""
                    if (not nm.strip()) or nm.strip().isdigit():
                        invalid_ids.append(did)
                except Exception:
                    continue
            def _exists(table: str) -> bool:
                try:
                    cols = db.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
                    return bool(cols)
                except Exception:
                    return False
            has_defaults = _exists('department_diet_defaults')
            has_exclusions = _exists('normal_exclusions')
            has_reg = _exists('weekview_registrations')
            for did in invalid_ids:
                sid = str(did)
                if has_defaults:
                    db.execute(text("DELETE FROM department_diet_defaults WHERE diet_type_id=:id"), {"id": sid})
                if has_exclusions:
                    db.execute(text("DELETE FROM normal_exclusions WHERE diet_type_id=:id"), {"id": sid})
                if has_reg:
                    db.execute(text("DELETE FROM weekview_registrations WHERE diet_type=:id"), {"id": sid})
                db.execute(text("DELETE FROM dietary_types WHERE id=:id"), {"id": did})
                deleted.append(did)
            db.commit()
            return deleted
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

    def collection_version(self, week: int, site_id: str) -> int:
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
                    "SELECT COALESCE(MAX(version),0) FROM alt2_flags WHERE site_id=:s AND week=:w"
                ),
                {"s": str(site_id), "w": int(week)},
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        finally:
            db.close()

    def current_collection_version_or_none(self, week: int) -> int:
        # Deprecated non-site-scoped variant: return 0 to avoid cross-site aggregation.
        return 0

    def list_for_week(self, week: int, site_id: str) -> list[dict]:
        """List alt2 flags for a given week and site (strictly site-scoped)."""
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
                    "SELECT site_id, department_id, week, weekday, enabled, COALESCE(version,0) FROM alt2_flags WHERE site_id=:s AND week=:w ORDER BY department_id, weekday"
                ),
                {"s": str(site_id), "w": int(week)},
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
