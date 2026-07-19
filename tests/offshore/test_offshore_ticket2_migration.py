from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _upgrade_to_head(db_url: str) -> None:
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.upgrade(_alembic_cfg(db_url), "head")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


def _downgrade_to_base(db_url: str) -> None:
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.downgrade(_alembic_cfg(db_url), "base")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


def test_offshore_ticket2_migration_upgrade_downgrade_roundtrip(tmp_path):
    db_path = tmp_path / "offshore_migration.db"
    db_url = f"sqlite:///{db_path}"

    _upgrade_to_head(db_url)
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"offshore_installation_settings", "offshore_work_positions", "offshore_menu_cycles", "offshore_menu_cycle_slots"}.issubset(tables)

        assert inspector.get_unique_constraints("offshore_installation_settings")
        assert inspector.get_unique_constraints("offshore_work_positions")
        assert inspector.get_unique_constraints("offshore_menu_cycle_slots")

        settings_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_installation_settings")}
        work_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_work_positions")}
        cycle_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_menu_cycles")}
        slot_indexes = {idx["name"] for idx in inspector.get_indexes("offshore_menu_cycle_slots")}
        assert "ix_offshore_installation_settings_tenant_site" in settings_indexes
        assert "ix_offshore_work_positions_tenant_site_sort" in work_indexes
        assert "ix_offshore_work_positions_tenant_site_active" in work_indexes
        assert "ix_offshore_menu_cycles_tenant_site_active" in cycle_indexes
        assert "ix_offshore_menu_cycles_tenant_site_name" in cycle_indexes
        assert "ix_offshore_menu_cycle_slots_cycle_sort" in slot_indexes
        assert "ix_offshore_menu_cycle_slots_tenant_site" in slot_indexes

        with engine.begin() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_installation_settings")).scalar_one() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_work_positions")).scalar_one() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_menu_cycles")).scalar_one() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM offshore_menu_cycle_slots")).scalar_one() == 0
    finally:
        engine.dispose()

    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.downgrade(_alembic_cfg(db_url), "0025_add_commun_builder_publication_pins")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "offshore_installation_settings" not in tables
        assert "offshore_work_positions" not in tables
        assert "offshore_menu_cycles" not in tables
        assert "offshore_menu_cycle_slots" not in tables
    finally:
        engine.dispose()

    _upgrade_to_head(db_url)
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"offshore_installation_settings", "offshore_work_positions", "offshore_menu_cycles", "offshore_menu_cycle_slots"}.issubset(tables)
    finally:
        engine.dispose()
