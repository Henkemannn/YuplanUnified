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


def test_0036_upgrade_downgrade_and_reupgrade(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "department_requirement_groups_migration.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "0035_add_dietary_types_requirement_identity")
    command.stamp(_alembic_cfg(db_url), "0035_add_dietary_types_requirement_identity")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        assert "dietary_types" in inspector.get_table_names()
        assert "departments" in inspector.get_table_names()

        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        assert "department_requirement_groups" in inspector.get_table_names()
        assert "department_requirement_group_requirements" in inspector.get_table_names()

        assert _column_names(inspector, "department_requirement_groups") >= {
            "id",
            "department_id",
            "label",
            "default_quantity",
            "is_active",
            "created_at",
            "updated_at",
        }
        assert _column_names(inspector, "department_requirement_group_requirements") >= {
            "group_id",
            "dietary_type_id",
        }

        group_pk = inspector.get_pk_constraint("department_requirement_group_requirements")
        assert list(group_pk.get("constrained_columns") or []) == ["group_id", "dietary_type_id"]

        group_fks = inspector.get_foreign_keys("department_requirement_group_requirements")
        assert any(
            fk.get("referred_table") == "department_requirement_groups"
            and list(fk.get("constrained_columns") or []) == ["group_id"]
            for fk in group_fks
        )
        assert any(
            fk.get("referred_table") == "dietary_types"
            and list(fk.get("constrained_columns") or []) == ["dietary_type_id"]
            for fk in group_fks
        )

        group_table_fks = inspector.get_foreign_keys("department_requirement_groups")
        assert any(
            fk.get("referred_table") == "departments"
            and list(fk.get("constrained_columns") or []) == ["department_id"]
            for fk in group_table_fks
        )

        with engine.begin() as conn:
            conn.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES ('dept-1', 'site-1', 'Dept', 'fixed', 1, 0)"))
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, 1, 'site-1', 'Atomic', 'Övrigt', 'req-1', 'atomic', 0)"))
            conn.execute(text("INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('group-1', 'dept-1', 'G', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('group-1', 1)"))
            with pytest.raises(IntegrityError):
                conn.execute(text("INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('group-2', 'dept-1', 'G2', -1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))

        command.downgrade(_alembic_cfg(db_url), "0035_add_dietary_types_requirement_identity")

        inspector = inspect(engine)
        assert "department_requirement_groups" not in inspector.get_table_names()
        assert "department_requirement_group_requirements" not in inspector.get_table_names()
        assert "dietary_types" in inspector.get_table_names()
        assert "departments" in inspector.get_table_names()

        command.upgrade(_alembic_cfg(db_url), "head")
        inspector = inspect(engine)
        assert "department_requirement_groups" in inspector.get_table_names()
        assert "department_requirement_group_requirements" in inspector.get_table_names()
    finally:
        engine.dispose()