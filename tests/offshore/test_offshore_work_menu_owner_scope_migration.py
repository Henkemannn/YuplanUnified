from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_offshore_work_menu_owner_scope_migration_exposes_owner_scoped_unique_constraint(tmp_path: Path) -> None:
    db_path = tmp_path / "offshore_work_menu_owner_scope.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    command.upgrade(_alembic_cfg(db_url), "head")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("offshore_work_menu_decisions")}
        assert "owner_user_id" in columns

        unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("offshore_work_menu_decisions")}
        assert "uq_offshore_work_menu_decisions_event_track" not in unique_constraints
        assert "uq_offshore_work_menu_decisions_event_track_owner" in unique_constraints

        owner_constraint = next(
            constraint for constraint in inspector.get_unique_constraints("offshore_work_menu_decisions") if constraint["name"] == "uq_offshore_work_menu_decisions_event_track_owner"
        )
        assert owner_constraint["column_names"] == ["tenant_id", "site_id", "service_event_id", "menu_track_key", "owner_user_id"]

        index_names = {index["name"] for index in inspector.get_indexes("offshore_work_menu_decisions")}
        assert "ix_offshore_work_menu_decisions_tenant_site_event_owner" in index_names
    finally:
        engine.dispose()