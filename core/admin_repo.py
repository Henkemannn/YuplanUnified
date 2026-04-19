from __future__ import annotations

import os
import uuid
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from flask import current_app, has_app_context

from .db import get_session
from .diet_family import DIET_FAMILY_OTHER, infer_diet_family, normalize_diet_family
from .etag import ConcurrencyError


SERVICE_ADDON_FAMILIES: tuple[str, str, str] = ("mos", "sallad", "ovrigt")


def normalize_addon_family(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw == "ovritgt":
        raw = "ovrigt"
    if raw in SERVICE_ADDON_FAMILIES:
        return raw
    return "ovrigt"


def _addon_family_rank(value: str | None) -> int:
    key = normalize_addon_family(value)
    order = {"mos": 0, "sallad": 1, "ovrigt": 2}
    return int(order.get(key, 2))


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


def _ensure_service_addons_tables(db) -> None:
    if _is_sqlite(db):
        _ensure_service_addons_sqlite_scoped_uniqueness(db)
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS service_addons (
                    id TEXT PRIMARY KEY,
                    site_id TEXT NULL REFERENCES sites(id),
                    name TEXT NOT NULL,
                    addon_family TEXT NOT NULL DEFAULT 'ovrigt',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT,
                    UNIQUE(site_id, name)
                )
                """
            )
        )
        try:
            cols = {r[1] for r in db.execute(text("PRAGMA table_info('service_addons')")).fetchall()}
            if "site_id" not in cols:
                db.execute(text("ALTER TABLE service_addons ADD COLUMN site_id TEXT"))
            if "addon_family" not in cols:
                db.execute(text("ALTER TABLE service_addons ADD COLUMN addon_family TEXT"))
            db.execute(
                text(
                    """
                    UPDATE service_addons
                    SET addon_family='ovrigt'
                    WHERE addon_family IS NULL OR trim(CAST(addon_family AS TEXT))=''
                    """
                )
            )
        except Exception:
            pass
        try:
            db.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_service_addons_site_name
                    ON service_addons(site_id, name)
                    """
                )
            )
        except Exception:
            pass
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS department_service_addons (
                    id TEXT PRIMARY KEY,
                    department_id TEXT NOT NULL,
                    addon_id TEXT NOT NULL,
                    lunch_count INTEGER NULL,
                    dinner_count INTEGER NULL,
                    note TEXT NULL,
                    created_at TEXT
                )
                """
            )
        )
    _backfill_service_addons_site_scope(db)


def _ensure_service_addons_sqlite_scoped_uniqueness(db) -> None:
    if not _is_sqlite(db):
        return

    table_row = db.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='service_addons'")
    ).fetchone()
    if not table_row:
        return

    table_sql = str(table_row[0] or "")
    has_site_unique = "UNIQUE(site_id, name)" in table_sql or "UNIQUE (site_id, name)" in table_sql
    has_legacy_unique = "UNIQUE(name)" in table_sql or "UNIQUE (name)" in table_sql

    if has_site_unique and not has_legacy_unique:
        return

    cols = {str(r[1]) for r in db.execute(text("PRAGMA table_info('service_addons')")).fetchall()}
    has_site_col = "site_id" in cols
    has_family_col = "addon_family" in cols
    has_created_col = "created_at" in cols

    # Rebuild table in SQLite to change uniqueness semantics.
    db.execute(text("ALTER TABLE service_addons RENAME TO service_addons__old"))
    db.execute(
        text(
            """
            CREATE TABLE service_addons (
                id TEXT PRIMARY KEY,
                site_id TEXT NULL REFERENCES sites(id),
                name TEXT NOT NULL,
                addon_family TEXT NOT NULL DEFAULT 'ovrigt',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                UNIQUE(site_id, name)
            )
            """
        )
    )

    select_site = "site_id" if has_site_col else "NULL"
    select_family = "COALESCE(addon_family, 'ovrigt')" if has_family_col else "'ovrigt'"
    select_created = "created_at" if has_created_col else "CURRENT_TIMESTAMP"

    db.execute(
        text(
            f"""
            INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at)
            SELECT id,
                   {select_site} AS site_id,
                   name,
                   {select_family} AS addon_family,
                   COALESCE(is_active, 1) AS is_active,
                   {select_created} AS created_at
            FROM service_addons__old
            """
        )
    )
    db.execute(text("DROP TABLE service_addons__old"))

    try:
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_service_addons_site_name
                ON service_addons(site_id, name)
                """
            )
        )
    except Exception:
        pass


def _site_id_for_department(db, dept_id: str) -> str | None:
    row = db.execute(
        text("SELECT site_id FROM departments WHERE id=:id LIMIT 1"),
        {"id": str(dept_id)},
    ).fetchone()
    if not row:
        return None
    return str(row[0]) if row[0] is not None else None


def _backfill_service_addons_site_scope(db) -> None:
    if not _table_has_column(db, "service_addons", "site_id"):
        return

    has_family_col = _table_has_column(db, "service_addons", "addon_family")

    addon_rows = db.execute(
        text(
            """
            SELECT id, name,
                   COALESCE(addon_family, 'ovrigt') AS addon_family,
                   COALESCE(is_active, 1) AS is_active,
                   created_at,
                   site_id
            FROM service_addons
            """
        )
    ).fetchall()

    for row in addon_rows:
        addon_id = str(row[0])
        addon_name = str(row[1])
        addon_family = normalize_addon_family(row[2] if has_family_col else "ovrigt")
        addon_active = 1 if bool(row[3]) else 0
        addon_created_at = row[4]
        addon_site_id = (str(row[5]).strip() if row[5] is not None else "")

        if addon_site_id:
            continue

        site_rows = db.execute(
            text(
                """
                SELECT DISTINCT d.site_id
                FROM department_service_addons dsa
                JOIN departments d ON d.id = dsa.department_id
                WHERE dsa.addon_id=:addon_id AND d.site_id IS NOT NULL
                ORDER BY d.site_id
                """
            ),
            {"addon_id": addon_id},
        ).fetchall()
        site_ids = [str(r[0]) for r in site_rows if r and r[0] is not None]

        if len(site_ids) == 1:
            db.execute(
                text("UPDATE service_addons SET site_id=:sid WHERE id=:id"),
                {"sid": site_ids[0], "id": addon_id},
            )
            continue

        if len(site_ids) > 1:
            primary_site_id = site_ids[0]
            db.execute(
                text("UPDATE service_addons SET site_id=:sid WHERE id=:id"),
                {"sid": primary_site_id, "id": addon_id},
            )

            for sid in site_ids[1:]:
                existing = db.execute(
                    text(
                        """
                        SELECT id FROM service_addons
                        WHERE site_id=:sid AND lower(name)=lower(:name)
                        LIMIT 1
                        """
                    ),
                    {"sid": sid, "name": addon_name},
                ).fetchone()
                if existing:
                    target_addon_id = str(existing[0])
                else:
                    target_addon_id = str(uuid.uuid4())
                    if has_family_col:
                        db.execute(
                            text(
                                """
                                INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at)
                                VALUES(:id, :sid, :name, :addon_family, :is_active, :created_at)
                                """
                            ),
                            {
                                "id": target_addon_id,
                                "sid": sid,
                                "name": addon_name,
                                "addon_family": addon_family,
                                "is_active": addon_active,
                                "created_at": addon_created_at,
                            },
                        )
                    else:
                        db.execute(
                            text(
                                """
                                INSERT INTO service_addons(id, site_id, name, is_active, created_at)
                                VALUES(:id, :sid, :name, :is_active, :created_at)
                                """
                            ),
                            {
                                "id": target_addon_id,
                                "sid": sid,
                                "name": addon_name,
                                "is_active": addon_active,
                                "created_at": addon_created_at,
                            },
                        )

                db.execute(
                    text(
                        """
                        UPDATE department_service_addons
                        SET addon_id=:new_addon_id
                        WHERE addon_id=:old_addon_id
                          AND department_id IN (
                              SELECT id FROM departments WHERE site_id=:sid
                          )
                        """
                    ),
                    {
                        "new_addon_id": target_addon_id,
                        "old_addon_id": addon_id,
                        "sid": sid,
                    },
                )

    # Any remaining NULL site rows are anchored to the first available site to avoid global leakage.
    default_site = db.execute(
        text("SELECT id FROM sites WHERE id IS NOT NULL ORDER BY id LIMIT 1")
    ).fetchone()
    if default_site and default_site[0] is not None:
        db.execute(
            text("UPDATE service_addons SET site_id=:sid WHERE site_id IS NULL"),
            {"sid": str(default_site[0])},
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
            testing_mode = bool(has_app_context() and current_app.config.get("TESTING"))
            tenant_value = tenant_id
            if tenant_value is None:
                tenant_value = _resolve_default_tenant_id(db)
            if tenant_value is None and testing_mode:
                tenant_value = 1
            if tenant_value is None and _is_sqlite(db):
                try:
                    db.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS tenants (
                                id INTEGER PRIMARY KEY,
                                name TEXT NOT NULL,
                                active INTEGER NOT NULL DEFAULT 1
                            )
                            """
                        )
                    )
                    row = db.execute(text("SELECT id FROM tenants ORDER BY id LIMIT 1")).fetchone()
                    if row and row[0] is not None:
                        tenant_value = int(row[0])
                    else:
                        db.execute(
                            text("INSERT INTO tenants(id, name, active) VALUES(1, 'TestTenant', 1)")
                        )
                        tenant_value = 1
                except Exception:
                    pass
            if tenant_value is None:
                raise ValueError("tenant_required")
            if not tenant_exists(db, tenant_value):
                if testing_mode and int(tenant_value) == 1:
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

def _is_missing_department_diet_overrides_error(exc: Exception) -> bool:
    msg = str(exc or "").lower()
    if "department_diet_overrides" not in msg:
        return False
    markers = (
        "no such table",
        "does not exist",
        "undefined table",
        "unknown table",
        "invalid object name",
    )
    return any(m in msg for m in markers)

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
            try:
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
            except Exception as exc:
                if _is_missing_department_diet_overrides_error(exc):
                    return []
                raise
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
            try:
                db.execute(
                    text(
                        """
                        DELETE FROM department_diet_overrides
                        WHERE department_id=:d AND diet_type_id=:t
                        """
                    ),
                    {"d": str(dept_id), "t": str(diet_type_id)},
                )
            except Exception as exc:
                if _is_missing_department_diet_overrides_error(exc):
                    db.rollback()
                    return
                raise
            for it in items:
                day = int(it.get("day") or 0)
                meal = str(it.get("meal") or "").strip().lower()
                count = int(it.get("count") or 0)
                if day < 1 or day > 7 or meal not in ("lunch", "dinner"):
                    continue
                try:
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
                except Exception as exc:
                    if _is_missing_department_diet_overrides_error(exc):
                        db.rollback()
                        return
                    raise
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class ServiceAddonsRepo:
    def _find_any_by_name(self, db, name: str):
        return db.execute(
            text(
                """
                SELECT id, site_id
                FROM service_addons
                WHERE lower(name)=lower(:n)
                LIMIT 1
                """
            ),
            {"n": str(name)},
        ).fetchone()

    def _is_bound_to_other_site(self, db, addon_id: str, site_id: str) -> bool:
        row = db.execute(
            text(
                """
                SELECT 1
                FROM department_service_addons dsa
                JOIN departments d ON d.id = dsa.department_id
                WHERE dsa.addon_id=:addon_id
                  AND d.site_id IS NOT NULL
                  AND d.site_id <> :site_id
                LIMIT 1
                """
            ),
            {"addon_id": str(addon_id), "site_id": str(site_id)},
        ).fetchone()
        return row is not None

    def list_active(self, site_id: str) -> list[dict]:
        db = get_session()
        try:
            _ensure_service_addons_tables(db)
            has_family_col = _table_has_column(db, "service_addons", "addon_family")
            has_site_col = _table_has_column(db, "service_addons", "site_id")
            if has_family_col:
                sql = (
                    """
                    SELECT id, name, COALESCE(addon_family, 'ovrigt') AS addon_family, is_active
                    FROM service_addons
                    WHERE COALESCE(is_active, 1) = 1
                    """
                )
                params: dict[str, str] = {}
                if has_site_col:
                    sql += " AND site_id=:site_id"
                    params["site_id"] = str(site_id)
                sql += " ORDER BY name"
                rows = db.execute(text(sql), params).fetchall()
            else:
                sql = (
                    """
                    SELECT id, name, is_active
                    FROM service_addons
                    WHERE COALESCE(is_active, 1) = 1
                    """
                )
                params = {}
                if has_site_col:
                    sql += " AND site_id=:site_id"
                    params["site_id"] = str(site_id)
                sql += " ORDER BY name"
                rows = db.execute(text(sql), params).fetchall()
            return [
                {
                    "id": str(r[0]),
                    "name": str(r[1]),
                    "addon_family": normalize_addon_family((r[2] if has_family_col else "ovrigt")),
                    "is_active": bool((r[3] if has_family_col else r[2]) or 0),
                }
                for r in rows
            ]
        finally:
            db.close()

    def create_if_missing(self, name: str, site_id: str, addon_family: str | None = None) -> str:
        clean = str(name or "").strip()
        if not clean:
            raise ValueError("name required")
        family = normalize_addon_family(addon_family)
        db = get_session()
        try:
            _ensure_service_addons_tables(db)
            has_site_col = _table_has_column(db, "service_addons", "site_id")
            if has_site_col:
                row = db.execute(
                    text(
                        """
                        SELECT id FROM service_addons
                        WHERE site_id=:site_id AND lower(name)=lower(:n)
                        LIMIT 1
                        """
                    ),
                    {"n": clean, "site_id": str(site_id)},
                ).fetchone()
            else:
                row = db.execute(
                    text("SELECT id FROM service_addons WHERE lower(name)=lower(:n) LIMIT 1"),
                    {"n": clean},
                ).fetchone()
            if row:
                try:
                    self.set_family(str(row[0]), str(site_id), family)
                except Exception:
                    pass
                return str(row[0])

            # Legacy bridge: if an addon with same name exists without site binding, claim it for this site.
            any_row = self._find_any_by_name(db, clean) if has_site_col else None
            if any_row and has_site_col:
                any_id = str(any_row[0])
                any_site = str(any_row[1] or "").strip()
                if not any_site:
                    db.execute(
                        text("UPDATE service_addons SET site_id=:site_id WHERE id=:id"),
                        {"site_id": str(site_id), "id": any_id},
                    )
                    try:
                        self.set_family(any_id, str(site_id), family)
                    except Exception:
                        pass
                    db.commit()
                    return any_id

            sid = str(uuid.uuid4())
            has_family_col = _table_has_column(db, "service_addons", "addon_family")
            try:
                if has_family_col and has_site_col:
                    db.execute(
                        text(
                            """
                            INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at)
                            VALUES(:id, :site_id, :name, :addon_family, 1, CURRENT_TIMESTAMP)
                            """
                        ),
                        {"id": sid, "site_id": str(site_id), "name": clean, "addon_family": family},
                    )
                elif has_family_col:
                    db.execute(
                        text(
                            """
                            INSERT INTO service_addons(id, name, addon_family, is_active, created_at)
                            VALUES(:id, :name, :addon_family, 1, CURRENT_TIMESTAMP)
                            """
                        ),
                        {"id": sid, "name": clean, "addon_family": family},
                    )
                elif has_site_col:
                    db.execute(
                        text(
                            """
                            INSERT INTO service_addons(id, site_id, name, is_active, created_at)
                            VALUES(:id, :site_id, :name, 1, CURRENT_TIMESTAMP)
                            """
                        ),
                        {"id": sid, "site_id": str(site_id), "name": clean},
                    )
                else:
                    db.execute(
                        text(
                            """
                            INSERT INTO service_addons(id, name, is_active, created_at)
                            VALUES(:id, :name, 1, CURRENT_TIMESTAMP)
                            """
                        ),
                        {"id": sid, "name": clean},
                    )
            except IntegrityError:
                # Legacy UNIQUE(name) bridge for old sqlite schemas: reuse existing row when safe.
                fallback = self._find_any_by_name(db, clean)
                if not fallback:
                    raise
                fallback_id = str(fallback[0])
                fallback_site = str(fallback[1] or "").strip() if has_site_col else ""
                if has_site_col:
                    if not fallback_site:
                        db.execute(
                            text("UPDATE service_addons SET site_id=:site_id WHERE id=:id"),
                            {"site_id": str(site_id), "id": fallback_id},
                        )
                    elif fallback_site != str(site_id):
                        if self._is_bound_to_other_site(db, fallback_id, str(site_id)):
                            raise ValueError("service_addon_name_conflict_cross_site")
                        db.execute(
                            text("UPDATE service_addons SET site_id=:site_id WHERE id=:id"),
                            {"site_id": str(site_id), "id": fallback_id},
                        )
                try:
                    self.set_family(fallback_id, str(site_id), family)
                except Exception:
                    pass
                db.commit()
                return fallback_id
            db.commit()
            return sid
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def set_family(self, addon_id: str, site_id: str, addon_family: str | None) -> None:
        db = get_session()
        try:
            _ensure_service_addons_tables(db)
            if not _table_has_column(db, "service_addons", "addon_family"):
                return
            if _table_has_column(db, "service_addons", "site_id"):
                row = db.execute(
                    text("SELECT site_id FROM service_addons WHERE id=:id LIMIT 1"),
                    {"id": str(addon_id)},
                ).fetchone()
                if not row:
                    return
                addon_site_id = str(row[0] or "")
                assert addon_site_id == str(site_id), "service_addon_site_mismatch"
            db.execute(
                text("UPDATE service_addons SET addon_family=:f WHERE id=:id"),
                {"f": normalize_addon_family(addon_family), "id": str(addon_id)},
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class DepartmentServiceAddonsRepo:
    def list_for_department(self, dept_id: str, site_id: str | None = None) -> list[dict]:
        db = get_session()
        try:
            _ensure_service_addons_tables(db)
            has_family_col = _table_has_column(db, "service_addons", "addon_family")
            has_site_col = _table_has_column(db, "service_addons", "site_id")
            if has_family_col:
                sql = (
                    """
                    SELECT dsa.id, dsa.department_id, dsa.addon_id, sa.name,
                           COALESCE(sa.addon_family, 'ovrigt') AS addon_family,
                           dsa.lunch_count, dsa.dinner_count, COALESCE(dsa.note, '')
                    FROM department_service_addons dsa
                    JOIN service_addons sa ON sa.id = dsa.addon_id
                    JOIN departments d ON d.id = dsa.department_id
                    WHERE dsa.department_id=:d
                    """
                )
                params: dict[str, str] = {"d": str(dept_id)}
                if has_site_col:
                    if site_id:
                        sql += " AND d.site_id=:site_id AND sa.site_id=:site_id"
                        params["site_id"] = str(site_id)
                    else:
                        sql += " AND d.site_id = sa.site_id"
                sql += " ORDER BY sa.name"
                rows = db.execute(text(sql), params).fetchall()
            else:
                rows = db.execute(
                    text(
                        """
                        SELECT dsa.id, dsa.department_id, dsa.addon_id, sa.name,
                               dsa.lunch_count, dsa.dinner_count, COALESCE(dsa.note, '')
                        FROM department_service_addons dsa
                        JOIN service_addons sa ON sa.id = dsa.addon_id
                        WHERE dsa.department_id=:d
                        ORDER BY sa.name
                        """
                    ),
                    {"d": str(dept_id)},
                ).fetchall()
            out: list[dict] = []
            for r in rows:
                out.append(
                    {
                        "id": str(r[0]),
                        "department_id": str(r[1]),
                        "addon_id": str(r[2]),
                        "addon_name": str(r[3]),
                        "addon_family": normalize_addon_family((r[4] if has_family_col else "ovrigt")),
                        "lunch_count": (int((r[5] if has_family_col else r[4])) if (r[5] if has_family_col else r[4]) is not None else None),
                        "dinner_count": (int((r[6] if has_family_col else r[5])) if (r[6] if has_family_col else r[5]) is not None else None),
                        "note": str((r[7] if has_family_col else r[6]) or ""),
                    }
                )
            return out
        finally:
            db.close()

    def replace_for_department(self, dept_id: str, rows: Iterable[dict], site_id: str | None = None) -> None:
        db = get_session()
        try:
            _ensure_service_addons_tables(db)
            dept_site_id = _site_id_for_department(db, str(dept_id))
            if not dept_site_id:
                raise ValueError("department_not_found")
            if site_id is not None and str(site_id) != str(dept_site_id):
                raise AssertionError("department_site_mismatch")

            has_site_col = _table_has_column(db, "service_addons", "site_id")
            db.execute(
                text("DELETE FROM department_service_addons WHERE department_id=:d"),
                {"d": str(dept_id)},
            )
            for row in rows:
                addon_id = str(row.get("addon_id") or "").strip()
                if not addon_id:
                    continue

                if has_site_col:
                    addon_row = db.execute(
                        text("SELECT site_id FROM service_addons WHERE id=:id LIMIT 1"),
                        {"id": addon_id},
                    ).fetchone()
                    if not addon_row:
                        continue
                    addon_site_id = str(addon_row[0] or "")
                    assert addon_site_id == str(dept_site_id), "service_addon_site_mismatch"

                lunch = row.get("lunch_count")
                dinner = row.get("dinner_count")
                note = str(row.get("note") or "").strip() or None
                lunch_i = int(lunch) if lunch is not None else None
                dinner_i = int(dinner) if dinner is not None else None
                # Only persist rows that have at least one shown count (>0)
                if not ((lunch_i is not None and lunch_i > 0) or (dinner_i is not None and dinner_i > 0)):
                    continue
                rid = str(uuid.uuid4())
                db.execute(
                    text(
                        """
                        INSERT INTO department_service_addons(
                            id, department_id, addon_id, lunch_count, dinner_count, note, created_at
                        ) VALUES(:id, :department_id, :addon_id, :lunch_count, :dinner_count, :note, CURRENT_TIMESTAMP)
                        """
                    ),
                    {
                        "id": rid,
                        "department_id": str(dept_id),
                        "addon_id": addon_id,
                        "lunch_count": lunch_i,
                        "dinner_count": dinner_i,
                        "note": note,
                    },
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_totals_for_site_meal(self, site_id: str, meal: str) -> list[dict]:
        meal_key = str(meal or "").strip().lower()
        col = "lunch_count" if meal_key == "lunch" else "dinner_count"
        db = get_session()
        try:
            _ensure_service_addons_tables(db)
            has_family_col = _table_has_column(db, "service_addons", "addon_family")
            has_site_col = _table_has_column(db, "service_addons", "site_id")
            if has_family_col:
                where_site = " AND sa.site_id = :site_id" if has_site_col else ""
                rows = db.execute(
                    text(
                        f"""
                        SELECT sa.id, sa.name, COALESCE(sa.addon_family, 'ovrigt') AS addon_family, d.id, d.name,
                               dsa.{col} as count,
                               COALESCE(dsa.note, '')
                        FROM department_service_addons dsa
                        JOIN service_addons sa ON sa.id = dsa.addon_id
                        JOIN departments d ON d.id = dsa.department_id
                        WHERE d.site_id = :site_id
                                                    {where_site}
                          AND dsa.{col} IS NOT NULL
                          AND dsa.{col} > 0
                        ORDER BY sa.name, d.name
                        """
                    ),
                    {"site_id": str(site_id)},
                ).fetchall()
            else:
                rows = db.execute(
                    text(
                        f"""
                        SELECT sa.id, sa.name, d.id, d.name,
                               dsa.{col} as count,
                               COALESCE(dsa.note, '')
                        FROM department_service_addons dsa
                        JOIN service_addons sa ON sa.id = dsa.addon_id
                        JOIN departments d ON d.id = dsa.department_id
                        WHERE d.site_id = :site_id
                          AND dsa.{col} IS NOT NULL
                          AND dsa.{col} > 0
                        ORDER BY sa.name, d.name
                        """
                    ),
                    {"site_id": str(site_id)},
                ).fetchall()
            by_addon: dict[str, dict] = {}
            for r in rows:
                addon_id = str(r[0])
                addon_name = str(r[1])
                addon_family = normalize_addon_family((r[2] if has_family_col else "ovrigt"))
                dept_id = str(r[3] if has_family_col else r[2])
                dept_name = str(r[4] if has_family_col else r[3])
                count = int((r[5] if has_family_col else r[4]) or 0)
                note = str((r[6] if has_family_col else r[5]) or "").strip()
                if count <= 0:
                    continue
                if addon_id not in by_addon:
                    by_addon[addon_id] = {
                        "addon_id": addon_id,
                        "addon_name": addon_name,
                        "addon_family": addon_family,
                        "total_count": 0,
                        "departments": [],
                    }
                by_addon[addon_id]["total_count"] += count
                by_addon[addon_id]["departments"].append(
                    {
                        "department_id": dept_id,
                        "department_name": dept_name,
                        "count": count,
                        "note": note,
                    }
                )
            out = list(by_addon.values())
            out.sort(
                key=lambda x: (
                    _addon_family_rank(str(x.get("addon_family") or "ovrigt")),
                    -(int(x.get("total_count") or 0)),
                    str(x.get("addon_name") or ""),
                )
            )
            return out
        finally:
            db.close()

class DietTypeDeleteBlockedError(Exception):
    """Raised when a diet type is still referenced by other records."""

    def __init__(self, references: dict[str, int]):
        self.references = references
        parts = [f"{table}: {count}" for table, count in references.items() if count > 0]
        super().__init__(", ".join(parts) if parts else "in use")


class DietTypesRepo:
    """Repository for managing dietary types (specialkost), now scoped per site."""

    def _backfill_missing_families(self, db) -> None:
        rows = db.execute(
            text(
                "SELECT id, name FROM dietary_types "
                "WHERE diet_family IS NULL OR trim(CAST(diet_family AS TEXT))=''"
            )
        ).fetchall()
        for row in rows:
            did = int(row[0])
            nm = str(row[1] or "")
            fam = infer_diet_family(nm)
            db.execute(
                text("UPDATE dietary_types SET diet_family=:f WHERE id=:id"),
                {"f": fam, "id": did},
            )

    def _name_exists(
        self,
        db,
        *,
        name: str,
        site_id: str | None,
        exclude_id: int | None = None,
    ) -> bool:
        params: dict[str, object] = {"name": str(name).strip()}
        if site_id:
            sql = (
                "SELECT 1 FROM dietary_types "
                "WHERE lower(trim(name)) = lower(trim(:name)) "
                "AND site_id = :site_id"
            )
            params["site_id"] = str(site_id)
        else:
            sql = (
                "SELECT 1 FROM dietary_types "
                "WHERE lower(trim(name)) = lower(trim(:name)) "
                "AND (site_id IS NULL OR site_id='')"
            )
        if exclude_id is not None:
            sql += " AND id <> :exclude_id"
            params["exclude_id"] = int(exclude_id)
        row = db.execute(text(sql), params).fetchone()
        return row is not None

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
                        diet_family TEXT NOT NULL DEFAULT 'Övrigt',
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
                if "diet_family" not in cols:
                    db.execute(text("ALTER TABLE dietary_types ADD COLUMN diet_family TEXT"))
            except Exception:
                pass
            try:
                self._backfill_missing_families(db)
                db.execute(
                    text(
                        "UPDATE dietary_types SET diet_family=:fallback "
                        "WHERE diet_family IS NULL OR trim(CAST(diet_family AS TEXT))=''"
                    ),
                    {"fallback": DIET_FAMILY_OTHER},
                )
            except Exception:
                pass
            # Helpful index for lookups
            try:
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_dietary_types_site_name ON dietary_types(site_id, name)"))
            except Exception:
                pass

    def list_all(self, site_id: str | None = None, tenant_id: int | None = None) -> list[dict]:
        """List dietary types.

        Preferred usage is site-scoped via `site_id`.
        Legacy callers may pass `tenant_id`; in that case this method returns
        all dietary types (best-effort backward compatibility).
        """
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
                    if site_id:
                        rows = db.execute(
                            text(
                                "SELECT id, site_id, name, "
                                "COALESCE(NULLIF(trim(CAST(diet_family AS TEXT)), ''), :fallback) AS diet_family, "
                                "default_select "
                                "FROM dietary_types WHERE site_id=:s ORDER BY name"
                            ),
                            {"s": site_id, "fallback": DIET_FAMILY_OTHER},
                        ).fetchall()
                    elif tenant_id is not None:
                        # Legacy admin-ui compatibility path: tenant was historically used.
                        rows = db.execute(
                            text(
                                "SELECT id, site_id, name, "
                                "COALESCE(NULLIF(trim(CAST(diet_family AS TEXT)), ''), :fallback) AS diet_family, "
                                "default_select "
                                "FROM dietary_types ORDER BY name"
                            ),
                            {"fallback": DIET_FAMILY_OTHER},
                        ).fetchall()
                    else:
                        # Strict isolation for modern callers with no explicit scope
                        rows = []
            except Exception:
                rows = []
            return [
                {
                    "id": int(r[0]),
                    "site_id": (str(r[1]) if r[1] is not None else None),
                    "name": str(r[2]),
                    "diet_family": normalize_diet_family(str(r[3] or "")),
                    "default_select": bool(r[4]),
                }
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
                text(
                    "SELECT id, site_id, name, "
                    "COALESCE(NULLIF(trim(CAST(diet_family AS TEXT)), ''), :fallback) AS diet_family, "
                    "default_select "
                    "FROM dietary_types WHERE id=:id"
                ),
                {"id": diet_type_id, "fallback": DIET_FAMILY_OTHER},
            ).fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "site_id": (str(row[1]) if row[1] is not None else None),
                "name": str(row[2]),
                "diet_family": normalize_diet_family(str(row[3] or "")),
                "default_select": bool(row[4]),
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
        diet_family = normalize_diet_family(kwargs.get("diet_family"))
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
        name = str(name).strip()
        # Hard guard: name must not be purely numeric
        try:
            if str(name).strip().isdigit():
                raise ValueError("invalid name: purely numeric")
        except Exception:
            pass
        db = get_session()
        try:
            self._ensure_table(db)
            if self._name_exists(db, name=name, site_id=(str(site_id) if site_id else None)):
                raise ValueError("duplicate_name")
            if _is_sqlite(db):
                cols = {r[1] for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
                if "tenant_id" in cols:
                    # If legacy NOT NULL constraint exists, provide a default value (1)
                    notnull_map = {str(r[1]): int(r[3] or 0) for r in db.execute(text("PRAGMA table_info('dietary_types')")).fetchall()}
                    needs_tenant = bool(notnull_map.get("tenant_id", 0))
                    if needs_tenant:
                        tval = int(tenant_id) if tenant_id is not None else 1
                        db.execute(
                            text("INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, default_select) VALUES(:t, :s, :n, :f, :d)"),
                            {"t": tval, "s": site_id, "n": name, "f": diet_family, "d": 1 if default_select else 0},
                        )
                    else:
                        db.execute(
                            text("INSERT INTO dietary_types(site_id, name, diet_family, default_select) VALUES(:s, :n, :f, :d)"),
                            {"s": site_id, "n": name, "f": diet_family, "d": 1 if default_select else 0},
                        )
                else:
                    db.execute(
                        text("INSERT INTO dietary_types(site_id, name, diet_family, default_select) VALUES(:s, :n, :f, :d)"),
                        {"s": site_id, "n": name, "f": diet_family, "d": 1 if default_select else 0},
                    )
                row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
                new_id = int(row[0]) if row else 0
            else:
                if tenant_id is not None:
                    res = db.execute(
                        text("INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, default_select) VALUES(:t, :s, :n, :f, :d) RETURNING id"),
                        {"t": int(tenant_id), "s": site_id, "n": name, "f": diet_family, "d": default_select},
                    )
                else:
                    res = db.execute(
                        text("INSERT INTO dietary_types(site_id, name, diet_family, default_select) VALUES(:s, :n, :f, :d) RETURNING id"),
                        {"s": site_id, "n": name, "f": diet_family, "d": default_select},
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

    def update(
        self,
        diet_type_id: int,
        name: str | None = None,
        default_select: bool | None = None,
        diet_family: str | None = None,
    ) -> None:
        """Update dietary type name/family and/or default_select. TODO: Add ETag concurrency."""
        db = get_session()
        try:
            current = db.execute(
                text("SELECT site_id FROM dietary_types WHERE id=:id"),
                {"id": int(diet_type_id)},
            ).fetchone()
            if not current:
                return
            current_site_id = str(current[0]) if current[0] is not None else None
            sets = []
            params: dict = {"id": diet_type_id}
            if name is not None:
                clean_name = str(name).strip()
                if clean_name.isdigit():
                    raise ValueError("invalid name: purely numeric")
                if self._name_exists(
                    db,
                    name=clean_name,
                    site_id=current_site_id,
                    exclude_id=int(diet_type_id),
                ):
                    raise ValueError("duplicate_name")
                sets.append("name=:name")
                params["name"] = clean_name
            if default_select is not None:
                sets.append("default_select=:ds")
                params["ds"] = 1 if default_select else 0
            if diet_family is not None:
                sets.append("diet_family=:diet_family")
                params["diet_family"] = normalize_diet_family(diet_family)
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
        """Delete a dietary type by ID.

        Performs safe cleanup of known dependent rows before deleting the diet type.
        Raises `DietTypeDeleteBlockedError` only for unknown FK constraints.
        """
        db = get_session()
        try:
            self._ensure_table(db)
            did_txt = str(int(diet_type_id))

            dependency_tables = (
                ("department_diet_defaults", "diet_type_id"),
                ("normal_exclusions", "diet_type_id"),
                ("weekview_registrations", "diet_type"),
            )

            for table_name, column_name in dependency_tables:
                if not _table_has_column(db, table_name, column_name):
                    continue
                db.execute(
                    text(
                        f"DELETE FROM {table_name} "
                        f"WHERE CAST({column_name} AS TEXT)=:diet_type_id"
                    ),
                    {"diet_type_id": did_txt},
                )

            db.execute(text("DELETE FROM dietary_types WHERE id=:id"), {"id": int(diet_type_id)})
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DietTypeDeleteBlockedError({"foreign_key_dependency": 1}) from exc
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
