"""Add explicit site ownership to legacy dishes.

Revision ID: 0053_add_site_scope_to_dishes
Revises: 0052_add_site_id_to_notes
"""
from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision = "0053_add_site_scope_to_dishes"
down_revision = "0052_add_site_id_to_notes"
branch_labels = None
depends_on = None


def _assert_required_schema(connection) -> None:
    tables = set(inspect(connection).get_table_names())
    required = {"dishes", "menus", "menu_variants", "sites"}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError(f"dish site migration missing tables: {missing}")

    for table, columns in {
        "dishes": {"id", "tenant_id", "name", "category"},
        "menus": {"id", "tenant_id", "site_id"},
        "menu_variants": {"id", "menu_id", "dish_id"},
        "sites": {"id", "tenant_id"},
    }.items():
        actual = {column["name"] for column in inspect(connection).get_columns(table)}
        missing_columns = sorted(columns - actual)
        if missing_columns:
            raise RuntimeError(f"{table} missing required columns: {missing_columns}")


def _assert_menu_site_integrity(connection) -> None:
    invalid_sites = connection.execute(
        text(
            """
            SELECT m.id, m.tenant_id, m.site_id
            FROM menus m
            LEFT JOIN sites s ON s.id = m.site_id
            WHERE m.site_id IS NOT NULL
              AND (s.id IS NULL OR s.tenant_id IS NULL OR s.tenant_id <> m.tenant_id)
            LIMIT 10
            """
        )
    ).fetchall()
    if invalid_sites:
        raise RuntimeError(
            "dish site migration found invalid menu tenant/site relations: "
            f"{invalid_sites!r}"
        )

    cross_tenant = connection.execute(
        text(
            """
            SELECT mv.id, mv.dish_id, m.id, m.tenant_id, d.tenant_id
            FROM menu_variants mv
            JOIN menus m ON m.id = mv.menu_id
            JOIN dishes d ON d.id = mv.dish_id
            WHERE mv.dish_id IS NOT NULL
              AND m.tenant_id <> d.tenant_id
            LIMIT 10
            """
        )
    ).fetchall()
    if cross_tenant:
        raise RuntimeError(
            "dish site migration found cross-tenant menu relations: "
            f"{cross_tenant!r}"
        )


def _add_site_column(connection) -> None:
    with op.batch_alter_table("dishes", recreate="auto") as batch:
        batch.add_column(sa.Column("site_id", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_dishes_site_id",
            "sites",
            ["site_id"],
            ["id"],
        )
    op.create_index("ix_dishes_tenant_site", "dishes", ["tenant_id", "site_id"])


def _copy_multi_site_dishes(connection) -> None:
    rows = connection.execute(
        text(
            """
            SELECT d.id, d.tenant_id, d.name, d.category, m.site_id
            FROM dishes d
            JOIN menu_variants mv ON mv.dish_id = d.id
            JOIN menus m ON m.id = mv.menu_id
            WHERE m.site_id IS NOT NULL
            ORDER BY d.id, m.site_id
            """
        )
    ).fetchall()
    sites_by_dish: dict[int, set[str]] = defaultdict(set)
    dish_data: dict[int, tuple[int, str, str | None]] = {}
    for dish_id, tenant_id, name, category, site_id in rows:
        sites_by_dish[int(dish_id)].add(str(site_id))
        dish_data[int(dish_id)] = (int(tenant_id), str(name), category)

    for dish_id, site_ids in sites_by_dish.items():
        tenant_id, name, category = dish_data[dish_id]
        if len(site_ids) == 1:
            connection.execute(
                text("UPDATE dishes SET site_id = :site_id WHERE id = :dish_id"),
                {"site_id": next(iter(site_ids)), "dish_id": dish_id},
            )
            continue

        for site_id in sorted(site_ids):
            copied_id = connection.execute(
                text(
                    """
                    INSERT INTO dishes(tenant_id, site_id, name, category)
                    VALUES (:tenant_id, :site_id, :name, :category)
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "site_id": site_id,
                    "name": name,
                    "category": category,
                },
            ).scalar_one()
            connection.execute(
                text(
                    """
                    UPDATE menu_variants
                    SET dish_id = :copied_id
                    WHERE dish_id = :original_id
                      AND menu_id IN (
                          SELECT id FROM menus WHERE site_id = :site_id
                      )
                    """
                ),
                {
                    "copied_id": int(copied_id),
                    "original_id": dish_id,
                    "site_id": site_id,
                },
            )


def _assert_result(connection) -> None:
    invalid_dishes = connection.execute(
        text(
            """
            SELECT d.id, d.tenant_id, d.site_id, s.tenant_id
            FROM dishes d
            LEFT JOIN sites s ON s.id = d.site_id
            WHERE d.site_id IS NOT NULL
              AND (s.id IS NULL OR s.tenant_id <> d.tenant_id)
            LIMIT 10
            """
        )
    ).fetchall()
    if invalid_dishes:
        raise RuntimeError(
            "dish site migration produced invalid dish ownership: "
            f"{invalid_dishes!r}"
        )

    invalid_variants = connection.execute(
        text(
            """
            SELECT mv.id, mv.dish_id, m.site_id, d.site_id
            FROM menu_variants mv
            JOIN menus m ON m.id = mv.menu_id
            JOIN dishes d ON d.id = mv.dish_id
            WHERE m.site_id IS NOT NULL
              AND d.site_id IS NOT NULL
              AND m.site_id <> d.site_id
            LIMIT 10
            """
        )
    ).fetchall()
    if invalid_variants:
        raise RuntimeError(
            "dish site migration produced cross-site menu relations: "
            f"{invalid_variants!r}"
        )


def upgrade() -> None:
    connection = op.get_bind()
    _assert_required_schema(connection)
    _assert_menu_site_integrity(connection)
    _add_site_column(connection)
    _copy_multi_site_dishes(connection)
    _assert_result(connection)


def downgrade() -> None:
    op.drop_index("ix_dishes_tenant_site", table_name="dishes")
    with op.batch_alter_table("dishes", recreate="auto") as batch:
        batch.drop_constraint("fk_dishes_site_id", type_="foreignkey")
        batch.drop_column("site_id")
