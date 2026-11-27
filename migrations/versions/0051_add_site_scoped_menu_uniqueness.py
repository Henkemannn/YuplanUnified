"""Replace tenant-week menu uniqueness with site-scoped uniqueness.

Revision ID: 0051_add_site_scoped_menu_uniqueness
Revises: 0050_add_password_reset_storage
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision = "0051_add_site_scoped_menu_uniqueness"
down_revision = "0050_add_password_reset_storage"
branch_labels = None
depends_on = None

_REQUIRED_TABLES = {
    "tenants",
    "sites",
    "menus",
    "menu_variants",
    "commun_builder_menu_links",
    "commun_builder_publication_pins",
    "commun_builder_publication_revisions",
}
_LEGACY_UNIQUE_COLUMNS = ("tenant_id", "week", "year")
_TARGET_UNIQUE_COLUMNS = ("tenant_id", "site_id", "year", "week")


def _unique_definitions(connection) -> list[tuple[str, tuple[str, ...]]]:
    inspector = inspect(connection)
    definitions: list[tuple[str, tuple[str, ...]]] = []
    for constraint in inspector.get_unique_constraints("menus"):
        definitions.append(
            (
                f"constraint:{constraint.get('name') or '<unnamed>'}",
                tuple(constraint.get("column_names") or ()),
            )
        )
    for index in inspector.get_indexes("menus"):
        if index.get("unique") and not index.get("duplicates_constraint"):
            definitions.append(
                (
                    f"index:{index.get('name') or '<unnamed>'}",
                    tuple(index.get("column_names") or ()),
                )
            )
    return definitions


def _assert_version(connection, expected: str) -> None:
    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        raise RuntimeError("menu uniqueness migration requires alembic_version")
    versions = [
        row[0]
        for row in connection.execute(text("SELECT version_num FROM alembic_version"))
    ]
    if versions != [expected]:
        raise RuntimeError(
            "menu uniqueness migration requires exactly "
            f"{expected}; found {versions!r}"
        )


def _assert_required_schema(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise RuntimeError(f"menu uniqueness migration missing tables: {missing}")

    menu_columns = {
        column["name"]: column for column in inspector.get_columns("menus")
    }
    required_columns = {"id", "tenant_id", "site_id", "week", "year", "status", "updated_at"}
    missing_columns = sorted(required_columns - set(menu_columns))
    if missing_columns:
        raise RuntimeError(f"menus missing required columns: {missing_columns}")
    if not menu_columns["site_id"].get("nullable", True):
        raise RuntimeError("menus.site_id must remain nullable in this migration")


def _ensure_sites_tenant_id(connection) -> None:
    site_columns = {
        column["name"] for column in inspect(connection).get_columns("sites")
    }
    if "tenant_id" in site_columns:
        return

    op.add_column("sites", sa.Column("tenant_id", sa.Integer(), nullable=True))
    connection.execute(
        text(
            """
            UPDATE sites
            SET tenant_id = (
                SELECT MIN(m.tenant_id)
                FROM menus m
                WHERE m.site_id = sites.id
            )
            WHERE tenant_id IS NULL
              AND id IN (
                  SELECT m.site_id
                  FROM menus m
                  WHERE m.site_id IS NOT NULL
                  GROUP BY m.site_id
                  HAVING COUNT(DISTINCT m.tenant_id) = 1
              )
            """
        )
    )


def _assert_integrity(connection) -> None:
    if connection.dialect.name == "sqlite":
        integrity = connection.exec_driver_sql("PRAGMA integrity_check").scalar()
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        foreign_keys = connection.exec_driver_sql(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_keys:
            raise RuntimeError(f"SQLite foreign_key_check failed: {foreign_keys!r}")


def _assert_upgrade_data(connection) -> None:
    if connection.execute(
        text("SELECT COUNT(*) FROM menus WHERE site_id IS NULL")
    ).scalar_one():
        raise RuntimeError("menu uniqueness migration found menus with NULL site_id")

    invalid_menu_sites = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM menus m
            LEFT JOIN sites s ON s.id = m.site_id
            WHERE s.id IS NULL OR s.tenant_id IS NULL OR s.tenant_id <> m.tenant_id
            """
        )
    ).scalar_one()
    if invalid_menu_sites:
        raise RuntimeError(
            "menu uniqueness migration found invalid menu tenant/site relations"
        )

    duplicate_menus = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT tenant_id, site_id, year, week
                FROM menus
                GROUP BY tenant_id, site_id, year, week
                HAVING COUNT(*) > 1
            )
            """
        )
    ).scalar_one()
    if duplicate_menus:
        raise RuntimeError(
            "menu uniqueness migration found duplicate tenant/site/year/week menus"
        )

    for table in (
        "commun_builder_menu_links",
        "commun_builder_publication_pins",
        "commun_builder_publication_revisions",
    ):
        invalid_references = connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM {table} x
                JOIN menus m ON m.id = x.legacy_menu_id
                WHERE x.legacy_menu_id IS NOT NULL
                  AND (
                    m.site_id IS NULL
                    OR m.site_id <> x.site_id
                    OR m.tenant_id <> x.tenant_id
                  )
                """
            )
        ).scalar_one()
        if invalid_references:
            raise RuntimeError(
                f"menu uniqueness migration found invalid {table} menu references"
            )


def _assert_legacy_definition(connection) -> None:
    definitions = _unique_definitions(connection)
    if len(definitions) != 1 or definitions[0][1] != _LEGACY_UNIQUE_COLUMNS:
        raise RuntimeError(
            "menu uniqueness migration found unexpected menus uniqueness "
            f"definition: {definitions!r}"
        )


def _rebuild_menu_constraint(connection, *, downgrade: bool) -> None:
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("PRAGMA defer_foreign_keys=ON")

    recreate = "always" if connection.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("menus", recreate=recreate) as batch:
        if downgrade:
            batch.drop_constraint("uq_menu_tenant_site_year_week", type_="unique")
            batch.create_unique_constraint(
                "uq_menu_tenant_year_week",
                list(_LEGACY_UNIQUE_COLUMNS),
            )
        else:
            batch.drop_constraint("uq_menu_tenant_year_week", type_="unique")
            batch.create_unique_constraint(
                "uq_menu_tenant_site_year_week",
                list(_TARGET_UNIQUE_COLUMNS),
            )


def upgrade() -> None:
    connection = op.get_bind()
    _assert_version(connection, down_revision)
    _ensure_sites_tenant_id(connection)
    _assert_required_schema(connection)
    _assert_legacy_definition(connection)
    _assert_integrity(connection)
    _assert_upgrade_data(connection)
    _rebuild_menu_constraint(connection, downgrade=False)
    _assert_integrity(connection)


def downgrade() -> None:
    connection = op.get_bind()
    _assert_version(connection, revision)
    _assert_required_schema(connection)
    definitions = _unique_definitions(connection)
    if len(definitions) != 1 or definitions[0][1] != _TARGET_UNIQUE_COLUMNS:
        raise RuntimeError(
            "menu uniqueness downgrade found unexpected menus uniqueness "
            f"definition: {definitions!r}"
        )
    duplicate_legacy_keys = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT tenant_id, year, week
                FROM menus
                GROUP BY tenant_id, year, week
                HAVING COUNT(*) > 1
            )
            """
        )
    ).scalar_one()
    if duplicate_legacy_keys:
        raise RuntimeError(
            "menu uniqueness downgrade would recreate tenant/year/week collisions"
        )
    _assert_integrity(connection)
    _rebuild_menu_constraint(connection, downgrade=True)
    _assert_integrity(connection)
