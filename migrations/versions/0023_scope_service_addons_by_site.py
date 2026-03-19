"""Scope service addons by site and backfill existing rows

Revision ID: 0023_scope_service_addons_by_site
Revises: 0022_add_pilot_activity_events
Create Date: 2026-03-18
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0023_scope_service_addons_by_site"
down_revision = "0022_add_pilot_activity_events"
branch_labels = None
depends_on = None


def _column_names(inspector) -> set[str]:
    try:
        return {str(c["name"]) for c in inspector.get_columns("service_addons")}
    except Exception:
        return set()


def _sqlite_rebuild_service_addons(conn) -> None:
    cols = {str(r[1]) for r in conn.execute(sa.text("PRAGMA table_info('service_addons')")).fetchall()}
    has_site_col = "site_id" in cols
    has_family_col = "addon_family" in cols
    has_created_col = "created_at" in cols

    conn.execute(sa.text("ALTER TABLE service_addons RENAME TO service_addons__old"))
    conn.execute(
        sa.text(
            """
            CREATE TABLE service_addons (
                id TEXT PRIMARY KEY,
                site_id TEXT NULL,
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

    conn.execute(
        sa.text(
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
    conn.execute(sa.text("DROP TABLE service_addons__old"))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "service_addons" not in table_names:
        return

    if conn.dialect.name == "sqlite":
        _sqlite_rebuild_service_addons(conn)
        _backfill_site_scope(conn)
        try:
            conn.execute(
                sa.text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_service_addons_site_name "
                    "ON service_addons(site_id, name)"
                )
            )
        except Exception:
            pass
        try:
            op.create_index("idx_service_addons_site_id", "service_addons", ["site_id"], unique=False)
        except Exception:
            pass
        return

    cols = _column_names(inspector)
    if "site_id" not in cols:
        op.add_column("service_addons", sa.Column("site_id", sa.String(length=64), nullable=True))

    try:
        op.create_foreign_key(
            "fk_service_addons_site_id",
            "service_addons",
            "sites",
            ["site_id"],
            ["id"],
        )
    except Exception:
        pass

    # Remove legacy global unique(name) so we can safely split rows by site.
    try:
        op.drop_constraint("uq_service_addons_name", "service_addons", type_="unique")
    except Exception:
        try:
            conn.execute(sa.text("DROP INDEX IF EXISTS uq_service_addons_name"))
        except Exception:
            pass

    has_family = "addon_family" in _column_names(inspector)

    addon_rows = conn.execute(
        sa.text(
            """
            SELECT id, name, COALESCE(addon_family, 'ovrigt') AS addon_family,
                   COALESCE(is_active, 1) AS is_active,
                   created_at, site_id
            FROM service_addons
            """
        )
    ).fetchall()

    for row in addon_rows:
        addon_id = str(row[0])
        addon_name = str(row[1])
        addon_family = str(row[2] or "ovrigt")
        is_active = bool(row[3])
        created_at = row[4]
        site_id = str(row[5]).strip() if row[5] is not None else ""
        if site_id:
            continue

        sites = conn.execute(
            sa.text(
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
        site_ids = [str(r[0]) for r in sites if r and r[0] is not None]

        if len(site_ids) == 1:
            conn.execute(
                sa.text("UPDATE service_addons SET site_id=:sid WHERE id=:id"),
                {"sid": site_ids[0], "id": addon_id},
            )
            continue

        if len(site_ids) > 1:
            primary_site = site_ids[0]
            conn.execute(
                sa.text("UPDATE service_addons SET site_id=:sid WHERE id=:id"),
                {"sid": primary_site, "id": addon_id},
            )
            for sid in site_ids[1:]:
                existing = conn.execute(
                    sa.text(
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
                    if has_family:
                        conn.execute(
                            sa.text(
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
                                "is_active": is_active,
                                "created_at": created_at,
                            },
                        )
                    else:
                        conn.execute(
                            sa.text(
                                """
                                INSERT INTO service_addons(id, site_id, name, is_active, created_at)
                                VALUES(:id, :sid, :name, :is_active, :created_at)
                                """
                            ),
                            {
                                "id": target_addon_id,
                                "sid": sid,
                                "name": addon_name,
                                "is_active": is_active,
                                "created_at": created_at,
                            },
                        )

                conn.execute(
                    sa.text(
                        """
                        UPDATE department_service_addons
                        SET addon_id=:new_id
                        WHERE addon_id=:old_id
                          AND department_id IN (SELECT id FROM departments WHERE site_id=:sid)
                        """
                    ),
                    {"new_id": target_addon_id, "old_id": addon_id, "sid": sid},
                )

    default_site = conn.execute(
        sa.text("SELECT id FROM sites WHERE id IS NOT NULL ORDER BY id LIMIT 1")
    ).fetchone()
    if default_site and default_site[0] is not None:
        conn.execute(
            sa.text("UPDATE service_addons SET site_id=:sid WHERE site_id IS NULL"),
            {"sid": str(default_site[0])},
        )

    try:
        op.create_unique_constraint(
            "uq_service_addons_site_name",
            "service_addons",
            ["site_id", "name"],
        )
    except Exception:
        try:
            conn.execute(
                sa.text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_service_addons_site_name "
                    "ON service_addons(site_id, name)"
                )
            )
        except Exception:
            pass

    try:
        op.create_index("idx_service_addons_site_id", "service_addons", ["site_id"], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "service_addons" not in table_names:
        return

    try:
        op.drop_index("idx_service_addons_site_id", table_name="service_addons")
    except Exception:
        pass

    try:
        op.drop_constraint("fk_service_addons_site_id", "service_addons", type_="foreignkey")
    except Exception:
        pass

    try:
        op.drop_constraint("uq_service_addons_site_name", "service_addons", type_="unique")
    except Exception:
        try:
            conn.execute(sa.text("DROP INDEX IF EXISTS uq_service_addons_site_name"))
        except Exception:
            pass

    # Best effort restore old uniqueness.
    try:
        op.create_unique_constraint("uq_service_addons_name", "service_addons", ["name"])
    except Exception:
        try:
            conn.execute(
                sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_service_addons_name ON service_addons(name)")
            )
        except Exception:
            pass

    try:
        op.drop_column("service_addons", "site_id")
    except Exception:
        pass
