from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def test_0044_upgrade_downgrade_and_reupgrade(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "department_menu_row_demand_migration.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "0043_add_commun_builder_publication_revisions")
    command.stamp(_alembic_cfg(db_url), "0043_add_commun_builder_publication_revisions")

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants(id, name) VALUES (1, 'Tenant 1')"))
            conn.execute(text("INSERT INTO sites(id, name, version) VALUES ('site-demand', 'Demand Site', 0)"))
            conn.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES ('dept-demand', 'site-demand', 'Demand Dept', 'manual', 10, 0)"
                )
            )
            conn.execute(
                text("INSERT INTO menus(id, tenant_id, site_id, week, year, status) VALUES (1, 1, 'site-demand', 16, 2026, 'published')")
            )

        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        assert "department_menu_row_demands" in inspector.get_table_names()
        assert _column_names(inspector, "department_menu_row_demands") >= {
            "id",
            "tenant_id",
            "site_id",
            "department_id",
            "year",
            "week",
            "weekday",
            "builder_menu_id",
            "builder_menu_version",
            "builder_menu_row_id",
            "selection_group_id",
            "quantity",
            "created_at",
            "updated_at",
        }

        pk = inspector.get_pk_constraint("department_menu_row_demands")
        assert list(pk.get("constrained_columns") or []) == ["id"]

        uqs = inspector.get_unique_constraints("department_menu_row_demands")
        assert any(
            uq.get("name") == "uq_department_menu_row_demands_business_key"
            and list(uq.get("column_names") or []) == [
                "tenant_id",
                "site_id",
                "department_id",
                "year",
                "week",
                "weekday",
                "builder_menu_id",
                "builder_menu_version",
                "builder_menu_row_id",
            ]
            for uq in uqs
        )

        fks = inspector.get_foreign_keys("department_menu_row_demands")
        assert any(fk.get("referred_table") == "tenants" for fk in fks)
        assert any(fk.get("referred_table") == "sites" for fk in fks)
        assert any(fk.get("referred_table") == "departments" for fk in fks)

        indexes = {index["name"] for index in inspector.get_indexes("department_menu_row_demands")}
        assert "ix_department_menu_row_demands_department_id" in indexes
        assert "ix_department_menu_row_demands_builder_menu_row_id" in indexes

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO department_menu_row_demands("
                    "tenant_id, site_id, department_id, year, week, weekday, builder_menu_id, builder_menu_version, builder_menu_row_id, selection_group_id, quantity, created_at, updated_at"
                    ") VALUES (1, 'site-demand', 'dept-demand', 2026, 16, 1, 'builder-menu-demand', 1, 'builder-menu-demand-row-a', 'grp_x', 14, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO department_menu_row_demands("
                    "tenant_id, site_id, department_id, year, week, weekday, builder_menu_id, builder_menu_version, builder_menu_row_id, selection_group_id, quantity, created_at, updated_at"
                    ") VALUES (1, 'site-demand', 'dept-demand', 2026, 16, 1, 'builder-menu-demand', 1, 'builder-menu-demand-row-b', 'grp_x', 4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO department_menu_row_demands("
                    "tenant_id, site_id, department_id, year, week, weekday, builder_menu_id, builder_menu_version, builder_menu_row_id, selection_group_id, quantity, created_at, updated_at"
                    ") VALUES (1, 'site-demand', 'dept-demand', 2026, 16, 2, 'builder-menu-demand', 1, 'builder-menu-demand-row-fixed', NULL, 7, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO department_menu_row_demands("
                        "tenant_id, site_id, department_id, year, week, weekday, builder_menu_id, builder_menu_version, builder_menu_row_id, selection_group_id, quantity, created_at, updated_at"
                        ") VALUES (1, 'site-demand', 'dept-demand', 2026, 16, 1, 'builder-menu-demand', 1, 'builder-menu-demand-row-a', 'grp_x', 9, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    )
                )
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO department_menu_row_demands("
                        "tenant_id, site_id, department_id, year, week, weekday, builder_menu_id, builder_menu_version, builder_menu_row_id, selection_group_id, quantity, created_at, updated_at"
                        ") VALUES (1, 'site-demand', 'dept-demand', 2026, 16, 1, 'builder-menu-demand', 1, 'builder-menu-demand-row-negative', 'grp_x', -1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    )
                )

        with engine.begin() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM menus")).fetchone()[0]
            assert int(count) == 1

        command.downgrade(_alembic_cfg(db_url), "0043_add_commun_builder_publication_revisions")
        inspector = inspect(engine)
        assert "department_menu_row_demands" not in inspector.get_table_names()
        assert "commun_builder_publication_revisions" in inspector.get_table_names()

        command.upgrade(_alembic_cfg(db_url), "head")
        inspector = inspect(engine)
        assert "department_menu_row_demands" in inspector.get_table_names()
    finally:
        engine.dispose()
