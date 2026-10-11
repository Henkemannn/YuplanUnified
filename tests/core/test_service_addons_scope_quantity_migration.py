from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_0047_migration_backfills_service_addon_scope_and_mode(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "service_addons_scope_quantity_migration.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "0046_add_user_must_change_password")
    command.stamp(_alembic_cfg(db_url), "0046_add_user_must_change_password")

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO sites(id, name) VALUES('site-1', 'Site 1')"))
            conn.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES('dept-1', 'site-1', 'Dept 1', 'fixed', 10, 0)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at) "
                    "VALUES('addon-lunch', 'site-1', 'Lunch only', 'ovrigt', 1, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at) "
                    "VALUES('addon-dinner', 'site-1', 'Dinner only', 'ovrigt', 1, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at) "
                    "VALUES('addon-both', 'site-1', 'Both meals', 'ovrigt', 1, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO department_service_addons(id, department_id, addon_id, lunch_count, dinner_count, note, created_at) "
                    "VALUES('row-lunch', 'dept-1', 'addon-lunch', 5, 0, 'lunch', CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO department_service_addons(id, department_id, addon_id, lunch_count, dinner_count, note, created_at) "
                    "VALUES('row-dinner', 'dept-1', 'addon-dinner', 0, 6, 'dinner', CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO department_service_addons(id, department_id, addon_id, lunch_count, dinner_count, note, created_at) "
                    "VALUES('row-both', 'dept-1', 'addon-both', 4, 3, 'both', CURRENT_TIMESTAMP)"
                )
            )

        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        cols = {column["name"] for column in inspector.get_columns("department_service_addons")}
        assert {"service_scope", "quantity_mode", "lunch_count", "dinner_count"}.issubset(cols)

        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, service_scope, quantity_mode, lunch_count, dinner_count "
                    "FROM department_service_addons ORDER BY id"
                )
            ).fetchall()

        assert rows == [
            ("row-both", "all_services", "custom", 4, 3),
            ("row-dinner", "dinner", "custom", None, 6),
            ("row-lunch", "lunch", "custom", 5, None),
        ]
    finally:
        engine.dispose()
