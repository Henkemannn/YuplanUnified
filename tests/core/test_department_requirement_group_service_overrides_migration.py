from __future__ import annotations

import logging
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


def _seed_0036_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES ('dept-1', 'site-1', 'Dept', 'fixed', 1, 0)"))
        conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, 1, 'site-1', 'Atomic', 'Övrigt', 'req-1', 'atomic', 0)"))
        conn.execute(text("INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('group-1', 'dept-1', 'G', 2, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))


def test_0037_upgrade_downgrade_and_reupgrade(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "department_requirement_group_service_overrides_migration.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "0036_add_department_requirement_groups")
    command.stamp(_alembic_cfg(db_url), "0036_add_department_requirement_groups")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        assert "department_requirement_groups" in inspector.get_table_names()
        assert "department_requirement_group_requirements" in inspector.get_table_names()

        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        assert "department_requirement_group_service_overrides" in inspector.get_table_names()

        assert _column_names(inspector, "department_requirement_group_service_overrides") >= {
            "group_id",
            "service_date",
            "meal_key",
            "quantity",
            "created_at",
            "updated_at",
        }

        pk = inspector.get_pk_constraint("department_requirement_group_service_overrides")
        assert list(pk.get("constrained_columns") or []) == ["group_id", "service_date", "meal_key"]

        fks = inspector.get_foreign_keys("department_requirement_group_service_overrides")
        assert any(
            fk.get("referred_table") == "department_requirement_groups"
            and list(fk.get("constrained_columns") or []) == ["group_id"]
            for fk in fks
        )

        checks = {constraint.get("name") for constraint in inspector.get_check_constraints("department_requirement_group_service_overrides")}
        assert "ck_department_requirement_group_service_overrides_quantity_non_negative" in checks
        assert "ck_department_requirement_group_service_overrides_meal_key_not_empty" in checks
        assert "ck_department_requirement_group_service_overrides_meal_key_normalized" in checks

        _seed_0036_schema(engine)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO department_requirement_group_service_overrides(group_id, service_date, meal_key, quantity, created_at, updated_at) VALUES ('group-1', '2026-09-08', 'lunch', 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            with pytest.raises(IntegrityError):
                conn.execute(text("INSERT INTO department_requirement_group_service_overrides(group_id, service_date, meal_key, quantity, created_at, updated_at) VALUES ('group-1', '2026-09-08', 'dinner', -1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))

        command.downgrade(_alembic_cfg(db_url), "0036_add_department_requirement_groups")
        inspector = inspect(engine)
        assert "department_requirement_group_service_overrides" not in inspector.get_table_names()
        assert "department_requirement_groups" in inspector.get_table_names()
        assert "department_requirement_group_requirements" in inspector.get_table_names()

        command.upgrade(_alembic_cfg(db_url), "head")
        inspector = inspect(engine)
        assert "department_requirement_group_service_overrides" in inspector.get_table_names()
    finally:
        engine.dispose()


def test_fresh_head_upgrade_creates_0037_schema(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "fresh_department_requirement_group_service_overrides.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "head")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        assert "department_requirement_group_service_overrides" in inspector.get_table_names()
        assert "department_requirement_groups" in inspector.get_table_names()
        assert "department_requirement_group_requirements" in inspector.get_table_names()
    finally:
        engine.dispose()


def test_head_upgrade_does_not_disable_existing_loggers(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "logger_isolation_department_requirement_group_service_overrides.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    probe_logger = logging.getLogger("alembic.logger.isolation.probe")
    previous_state = {
        "handlers": list(probe_logger.handlers),
        "filters": list(probe_logger.filters),
        "level": probe_logger.level,
        "propagate": probe_logger.propagate,
        "disabled": probe_logger.disabled,
    }
    probe_logger.disabled = False

    try:
        command.upgrade(_alembic_cfg(db_url), "head")
        assert probe_logger.disabled is False
    finally:
        probe_logger.handlers = list(previous_state["handlers"])
        probe_logger.filters = list(previous_state["filters"])
        probe_logger.setLevel(int(previous_state["level"]))
        probe_logger.propagate = bool(previous_state["propagate"])
        probe_logger.disabled = bool(previous_state["disabled"])
