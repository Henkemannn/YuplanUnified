from __future__ import annotations

import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_fresh_upgrade_adds_dietary_types_site_id_and_index(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "fresh_dietary_types_site_id.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "head")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("dietary_types")}
        assert "site_id" in columns
        assert "diet_family" in columns

        equivalent_indexes = [
            index
            for index in inspector.get_indexes("dietary_types")
            if list(index.get("column_names") or []) == ["site_id", "name"]
        ]
        assert len(equivalent_indexes) == 1
        assert equivalent_indexes[0]["name"] == "idx_dietary_types_site_name"
    finally:
        engine.dispose()


def test_legacy_rows_survive_site_id_migration_with_null_site(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "legacy_dietary_types_site_id.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE dietary_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NULL,
                        name TEXT NOT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            conn.execute(text("INSERT INTO dietary_types(tenant_id, name, default_select) VALUES (1, 'Laktos och gluten', 0)"))

        command.stamp(_alembic_cfg(db_url), "0033_add_users_department_id")
        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("dietary_types")}
        assert "site_id" in columns

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, name, site_id FROM dietary_types WHERE name=:name"),
                {"name": "Laktos och gluten"},
            ).fetchone()
        assert row is not None
        assert int(row[0]) == 1
        assert row[1] == "Laktos och gluten"
        assert row[2] is None
    finally:
        engine.dispose()


def test_existing_site_id_schema_is_left_intact(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "existing_site_id_dietary_types.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    site_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE dietary_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NULL,
                        site_id TEXT NULL,
                        name TEXT NOT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0,
                        diet_family TEXT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX idx_dietary_types_site_name ON dietary_types(site_id, name)"))
            conn.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, default_select, diet_family) VALUES (1, :site_id, 'Glutenfri', 1, 'Allergi / Exkludering')"
                ),
                {"site_id": site_id},
            )

        command.stamp(_alembic_cfg(db_url), "0033_add_users_department_id")
        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("dietary_types")}
        assert "site_id" in columns

        equivalent_indexes = [
            index
            for index in inspector.get_indexes("dietary_types")
            if list(index.get("column_names") or []) == ["site_id", "name"]
        ]
        assert len(equivalent_indexes) == 1
        assert equivalent_indexes[0]["name"] == "idx_dietary_types_site_name"

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, name, site_id, diet_family FROM dietary_types WHERE name=:name"),
                {"name": "Glutenfri"},
            ).fetchone()
        assert row is not None
        assert row[2] == site_id
        assert row[3] == "Allergi / Exkludering"
    finally:
        engine.dispose()


def test_equivalent_lookup_index_under_alternate_name_is_not_duplicated(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "alternate_lookup_index_dietary_types.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    site_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE dietary_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NULL,
                        site_id TEXT NULL,
                        name TEXT NOT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0,
                        diet_family TEXT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX legacy_lookup_idx ON dietary_types(site_id, name)"))
            conn.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, default_select, diet_family) VALUES (1, :site_id, 'Timbal', 0, 'Textur')"
                ),
                {"site_id": site_id},
            )

        command.stamp(_alembic_cfg(db_url), "0033_add_users_department_id")
        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        equivalent_indexes = [
            index
            for index in inspector.get_indexes("dietary_types")
            if list(index.get("column_names") or []) == ["site_id", "name"]
        ]
        assert len(equivalent_indexes) == 1
        assert equivalent_indexes[0]["name"] == "legacy_lookup_idx"

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT site_id, name FROM dietary_types WHERE name=:name"),
                {"name": "Timbal"},
            ).fetchone()
        assert row is not None
        assert row[0] == site_id
        assert row[1] == "Timbal"
    finally:
        engine.dispose()


def test_downgrade_is_non_destructive_for_existing_site_id_schema(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "downgrade_safe_dietary_types.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    site_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE dietary_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NULL,
                        site_id TEXT NULL,
                        name TEXT NOT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0,
                        diet_family TEXT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX idx_dietary_types_site_name ON dietary_types(site_id, name)"))
            conn.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, default_select, diet_family) VALUES (1, :site_id, 'Glutenfri', 1, 'Allergi / Exkludering')"
                ),
                {"site_id": site_id},
            )

        command.stamp(_alembic_cfg(db_url), "0033_add_users_department_id")
        command.upgrade(_alembic_cfg(db_url), "head")
        command.downgrade(_alembic_cfg(db_url), "0033_add_users_department_id")

        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("dietary_types")}
        assert "site_id" in columns

        equivalent_indexes = [
            index
            for index in inspector.get_indexes("dietary_types")
            if list(index.get("column_names") or []) == ["site_id", "name"]
        ]
        assert equivalent_indexes

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, name, site_id FROM dietary_types WHERE name=:name"),
                {"name": "Glutenfri"},
            ).fetchone()
        assert row is not None
        assert row[2] == site_id
    finally:
        engine.dispose()


def test_dietary_type_model_includes_site_id_and_diet_family() -> None:
    from core.models import DietaryType

    column_names = {column.name for column in DietaryType.__table__.columns}
    assert {"id", "tenant_id", "site_id", "name", "diet_family", "default_select"}.issubset(column_names)