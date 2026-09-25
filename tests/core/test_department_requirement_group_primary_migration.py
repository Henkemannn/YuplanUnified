from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def test_0039_adds_primary_requirement_and_backfills_singletons(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "department_requirement_group_primary_requirement_id.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "0038_add_planning_option_reviews")
    command.stamp(_alembic_cfg(db_url), "0038_add_planning_option_reviews")

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES ('dept-1', 'site-1', 'Dept', 'fixed', 1, 0)"))
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, 1, 'site-1', 'A', 'Övrigt', 'req-a', 'atomic', 0)"))
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (2, 1, 'site-1', 'B', 'Övrigt', 'req-b', 'atomic', 0)"))
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (3, 1, 'site-1', 'C', 'Övrigt', 'req-c', 'atomic', 0)"))
            conn.execute(text("INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('group-single', 'dept-1', 'Single', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('group-multi', 'dept-1', 'Multi', 2, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('group-empty', 'dept-1', 'Empty', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('group-single', 1)"))
            conn.execute(text("INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('group-multi', 2)"))
            conn.execute(text("INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('group-multi', 3)"))

        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        assert "department_requirement_groups" in inspector.get_table_names()
        assert _column_names(inspector, "department_requirement_groups") >= {
            "id",
            "department_id",
            "primary_requirement_id",
            "label",
            "default_quantity",
            "is_active",
            "created_at",
            "updated_at",
        }

        fks = inspector.get_foreign_keys("department_requirement_groups")
        assert any(
            fk.get("referred_table") == "dietary_types"
            and list(fk.get("constrained_columns") or []) == ["primary_requirement_id"]
            for fk in fks
        )

        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, primary_requirement_id FROM department_requirement_groups WHERE id IN ('group-single', 'group-multi', 'group-empty') ORDER BY id"
                )
            ).fetchall()
        assert {row[0]: row[1] for row in rows} == {
            "group-empty": None,
            "group-multi": None,
            "group-single": 1,
        }
    finally:
        engine.dispose()