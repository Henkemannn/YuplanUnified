from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from core.models import Base, Dish


ROOT = Path(__file__).resolve().parents[2]
REVISION = "0053_add_site_scope_to_dishes"
HEAD_REVISION = "0059_normal_exclusions_scope"
PREVIOUS_REVISION = "0052_add_site_id_to_notes"


def _config(target: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{target}")
    return config


def _upgrade_to_previous(target: Path, monkeypatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _config(target)
    command.upgrade(config, PREVIOUS_REVISION)
    return config


def _seed_site_data(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants(id, name, active) VALUES "
                "(9901, 'Dish Tenant', 1), (9902, 'Other Dish Tenant', 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO sites(id, name, tenant_id) VALUES "
                "('dish-site-a', 'Dish Site A', 9901), "
                "('dish-site-b', 'Dish Site B', 9901), "
                "('dish-site-c', 'Dish Site C', 9902)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO units(id, tenant_id, name, default_attendance) "
                "VALUES (9901, 9901, 'Dish Unit', 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO dishes(id, tenant_id, name, category) VALUES "
                "(9901, 9901, 'Single Site Dish', 'main'), "
                "(9902, 9901, 'Multi Site Dish', 'main'), "
                "(9903, 9901, 'Orphan Dish', 'side'), "
                "(9904, 9901, 'Unclassified Dish', 'dessert')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO menus(id, tenant_id, site_id, week, year, status) VALUES "
                "(9901, 9901, 'dish-site-a', 1, 2040, 'draft'), "
                "(9902, 9901, 'dish-site-b', 2, 2040, 'draft'), "
                "(9903, 9901, NULL, 3, 2040, 'draft')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO menu_variants(id, menu_id, day, meal, variant_type, dish_id) VALUES "
                "(9901, 9901, 'mon', 'lunch', 'main', 9901), "
                "(9902, 9901, 'tue', 'lunch', 'main', 9902), "
                "(9903, 9902, 'wed', 'lunch', 'main', 9902), "
                "(9904, 9903, 'thu', 'lunch', 'main', 9904)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks(id, tenant_id, task_type, title, dish_id) "
                "VALUES (9901, 9901, 'prep', 'Unclassified task', 9904)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO service_metrics("
                "id, tenant_id, unit_id, date, meal, dish_id"
                ") VALUES (9901, 9901, 9901, '2040-01-01', 'lunch', 9904)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO menu_overrides("
                "id, tenant_id, unit_id, date, meal, variant_type, replacement_dish_id, scope"
                ") VALUES (9901, 9901, NULL, '2040-01-01', 'lunch', 'main', 9904, 'private')"
            )
        )


def test_model_declares_nullable_site_scope_and_index():
    assert Dish.site_id.property.columns[0].nullable is True
    assert any(
        index.name == "ix_dishes_tenant_site"
        and tuple(column.name for column in index.columns) == ("tenant_id", "site_id")
        for index in Dish.__table__.indexes
    )


def test_migration_classifies_and_separates_historical_dishes(tmp_path, monkeypatch):
    target = tmp_path / "dish-site-scope.db"
    config = _upgrade_to_previous(target, monkeypatch)
    engine = create_engine(f"sqlite:///{target}")
    try:
        assert "site_id" not in {
            column["name"] for column in inspect(engine).get_columns("dishes")
        }
        _seed_site_data(engine)
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == HEAD_REVISION
            assert connection.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
            assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []

            assert connection.execute(
                text("SELECT site_id FROM dishes WHERE id=9901")
            ).scalar_one() == "dish-site-a"
            assert connection.execute(
                text("SELECT site_id FROM dishes WHERE id=9903")
            ).scalar_one() is None
            assert connection.execute(
                text("SELECT site_id FROM dishes WHERE id=9904")
            ).scalar_one() is None

            copies = connection.execute(
                text(
                    "SELECT site_id, name, category FROM dishes "
                    "WHERE name='Multi Site Dish' ORDER BY site_id"
                )
            ).fetchall()
            assert copies == [
                (None, "Multi Site Dish", "main"),
                ("dish-site-a", "Multi Site Dish", "main"),
                ("dish-site-b", "Multi Site Dish", "main"),
            ]
            assert connection.execute(
                text("SELECT site_id FROM dishes WHERE id=9902")
            ).scalar_one() is None

            relinked = connection.execute(
                text(
                    "SELECT m.site_id, d.site_id "
                    "FROM menu_variants mv "
                    "JOIN menus m ON m.id=mv.menu_id "
                    "JOIN dishes d ON d.id=mv.dish_id "
                    "WHERE mv.id IN (9902, 9903) ORDER BY m.site_id"
                )
            ).fetchall()
            assert relinked == [
                ("dish-site-a", "dish-site-a"),
                ("dish-site-b", "dish-site-b"),
            ]
            assert connection.execute(
                text("SELECT dish_id FROM menu_variants WHERE id=9904")
            ).scalar_one() == 9904

            assert connection.execute(
                text("SELECT COUNT(*) FROM tasks WHERE dish_id=9904")
            ).scalar_one() == 1
            assert connection.execute(
                text("SELECT COUNT(*) FROM service_metrics WHERE dish_id=9904")
            ).scalar_one() == 1
            assert connection.execute(
                text("SELECT COUNT(*) FROM menu_overrides WHERE replacement_dish_id=9904")
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_cross_tenant_menu_relation_fails_before_schema_change(tmp_path, monkeypatch):
    target = tmp_path / "dish-cross-tenant.db"
    config = _upgrade_to_previous(target, monkeypatch)
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tenants(id, name, active) VALUES "
                    "(9911, 'Tenant A', 1), (9912, 'Tenant B', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id) "
                    "VALUES ('cross-site-a', 'Cross Site A', 9911)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO dishes(id, tenant_id, name) "
                    "VALUES (9911, 9912, 'Foreign Dish')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO menus(id, tenant_id, site_id, week, year, status) "
                    "VALUES (9911, 9911, 'cross-site-a', 1, 2041, 'draft')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO menu_variants("
                    "id, menu_id, day, meal, variant_type, dish_id"
                    ") VALUES (9911, 9911, 'mon', 'lunch', 'main', 9911)"
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="cross-tenant menu relations"):
        command.upgrade(config, REVISION)

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == PREVIOUS_REVISION
            assert "site_id" not in {
                column["name"] for column in inspect(connection).get_columns("dishes")
            }
    finally:
        engine.dispose()


def test_downgrade_does_not_merge_site_copies(tmp_path, monkeypatch):
    target = tmp_path / "dish-downgrade.db"
    config = _upgrade_to_previous(target, monkeypatch)
    engine = create_engine(f"sqlite:///{target}")
    try:
        _seed_site_data(engine)
    finally:
        engine.dispose()

    command.upgrade(config, REVISION)
    command.downgrade(config, PREVIOUS_REVISION)
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" not in {
                column["name"] for column in inspect(connection).get_columns("dishes")
            }
            assert connection.execute(
                text("SELECT COUNT(*) FROM dishes WHERE name='Multi Site Dish'")
            ).scalar_one() == 3
            assert connection.execute(
                text("SELECT COUNT(*) FROM menu_variants")
            ).scalar_one() == 4
    finally:
        engine.dispose()
