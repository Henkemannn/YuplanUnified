from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
import pytest


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _equivalent_requirement_indexes(inspector) -> list[dict]:
    return [index for index in inspector.get_indexes("dietary_types") if list(index.get("column_names") or []) == ["requirement_key"]]


def _seed_legacy_dietary_types_table(conn, *, with_site_id: bool = False, with_requirement_fields: bool = False) -> None:
    if with_requirement_fields:
        conn.execute(
            text(
                """
                CREATE TABLE dietary_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER NULL,
                    site_id TEXT NULL,
                    name TEXT NOT NULL,
                    diet_family TEXT NULL,
                    requirement_key TEXT NULL,
                    semantics TEXT NULL,
                    default_select INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        return
    if with_site_id:
        conn.execute(
            text(
                """
                CREATE TABLE dietary_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER NULL,
                    site_id TEXT NULL,
                    name TEXT NOT NULL,
                    diet_family TEXT NULL,
                    default_select INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        return
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


def test_fresh_upgrade_adds_requirement_identity_and_unique_index(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "fresh_requirement_identity.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "head")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("dietary_types")}
        assert {"requirement_key", "semantics"}.issubset(columns)
        equivalent_indexes = _equivalent_requirement_indexes(inspector)
        assert len(equivalent_indexes) == 1
        assert equivalent_indexes[0]["name"] == "uq_dietary_types_requirement_key"
        assert bool(equivalent_indexes[0].get("unique")) is True
    finally:
        engine.dispose()


def test_legacy_service_create_keeps_legacy_bucket_and_stable_key(app_session) -> None:
    from core.diet_service import DietService
    from core.db import get_session

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("DELETE FROM unit_diet_assignments"))
            db.execute(text("DELETE FROM dietary_types"))
            db.commit()
        finally:
            db.close()

        service = DietService()
        diet_id = service.create_diet_type(tenant_id=1, name="Laktos och gluten", default_select=False)
        rows = service.list_diet_types(1)

        assert len(rows) == 1
        assert set(rows[0].keys()) == {"id", "name", "default_select"}
        assert rows[0]["name"] == "Laktos och gluten"
        assert rows[0]["default_select"] is False

        db = get_session()
        try:
            row = db.execute(
                text("SELECT id, name, semantics, requirement_key FROM dietary_types WHERE id=:id"),
                {"id": diet_id},
            ).fetchone()
        finally:
            db.close()

        assert row is not None
        assert row[1] == "Laktos och gluten"
        assert row[2] == "legacy_bucket"
        assert row[3] == f"legacy_{diet_id}"


def test_runtime_repair_stops_on_unknown_non_empty_semantics(app_session) -> None:
    from core.admin_repo import DietTypesRepo
    from core.db import get_session

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("DROP TABLE IF EXISTS dietary_types"))
            db.execute(
                text(
                    """
                    CREATE TABLE dietary_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NULL,
                        site_id TEXT NULL,
                        name TEXT NOT NULL,
                        diet_family TEXT NULL,
                        requirement_key TEXT NULL,
                        semantics TEXT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, requirement_key, semantics, default_select) VALUES (1, NULL, 'Mystery', 'legacy_99', 'mystery', 0)"
                )
            )
            db.commit()
            repo = DietTypesRepo()
            with pytest.raises(RuntimeError, match="invalid preexisting semantics"):
                repo.list_all(tenant_id=1)

            row = db.execute(
                text("SELECT requirement_key, semantics FROM dietary_types WHERE name='Mystery'")
            ).fetchone()
            assert row is not None
            assert row[0] == "legacy_99"
            assert row[1] == "mystery"
        finally:
            db.rollback()
            db.execute(text("DROP TABLE IF EXISTS dietary_types"))
            db.commit()
            db.close()


def test_existing_legacy_row_backfills_to_legacy_identity(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "legacy_requirement_identity.db"
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
                        site_id TEXT NULL,
                        name TEXT NOT NULL,
                        diet_family TEXT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, default_select) VALUES (1, 1, NULL, 'Gluten', 0)"))

        command.stamp(_alembic_cfg(db_url), "0034_add_dietary_types_site_id")
        command.upgrade(_alembic_cfg(db_url), "head")

        with engine.connect() as conn:
            row = conn.execute(text("SELECT id, name, site_id, requirement_key, semantics FROM dietary_types WHERE id=1")).fetchone()
        assert row is not None
        assert row[3] == "legacy_1"
        assert row[4] == "legacy_bucket"
    finally:
        engine.dispose()


def test_multiple_legacy_rows_get_unique_requirement_keys(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "multiple_legacy_identity.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            _seed_legacy_dietary_types_table(conn, with_site_id=False)
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, name, default_select) VALUES (1, 1, 'Glutenfri', 0)"))
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, name, default_select) VALUES (2, 1, 'Laktosfri', 0)"))

        command.stamp(_alembic_cfg(db_url), "0034_add_dietary_types_site_id")
        command.upgrade(_alembic_cfg(db_url), "head")

        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, requirement_key, semantics FROM dietary_types ORDER BY id")
            ).fetchall()

        assert [row[1] for row in rows] == ["legacy_1", "legacy_2"]
        assert [row[2] for row in rows] == ["legacy_bucket", "legacy_bucket"]
        assert len({row[1] for row in rows}) == 2
    finally:
        engine.dispose()


def test_existing_equivalent_requirement_index_is_not_duplicated(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "existing_req_index.db"
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
                        site_id TEXT NULL,
                        name TEXT NOT NULL,
                        diet_family TEXT NULL,
                        requirement_key TEXT NULL,
                        semantics TEXT NULL,
                        default_select INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            conn.execute(text("CREATE UNIQUE INDEX legacy_requirement_key_idx ON dietary_types(requirement_key)"))
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, requirement_key, semantics, default_select) VALUES (7, 1, NULL, 'Timbal', 'legacy_7', 'legacy_bucket', 0)"))

        command.stamp(_alembic_cfg(db_url), "0034_add_dietary_types_site_id")
        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        equivalent_indexes = _equivalent_requirement_indexes(inspector)
        assert len(equivalent_indexes) == 1
        assert equivalent_indexes[0]["name"] == "legacy_requirement_key_idx"
    finally:
        engine.dispose()


def test_duplicate_preexisting_requirement_key_stops_migration(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "duplicate_requirement_key.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            _seed_legacy_dietary_types_table(conn, with_requirement_fields=True)
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, requirement_key, semantics, default_select) VALUES (1, 1, NULL, 'A', 'legacy_1', 'legacy_bucket', 0)"))
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, requirement_key, semantics, default_select) VALUES (2, 1, NULL, 'B', 'legacy_1', 'legacy_bucket', 0)"))

        command.stamp(_alembic_cfg(db_url), "0034_add_dietary_types_site_id")
        with pytest.raises(RuntimeError, match="duplicate requirement_key values"):
            command.upgrade(_alembic_cfg(db_url), "head")
    finally:
        engine.dispose()


def test_invalid_preexisting_semantics_stops_migration(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "invalid_semantics.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            _seed_legacy_dietary_types_table(conn, with_requirement_fields=True)
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, requirement_key, semantics, default_select) VALUES (1, 1, NULL, 'A', 'legacy_1', 'mystery', 0)"))

        command.stamp(_alembic_cfg(db_url), "0034_add_dietary_types_site_id")
        with pytest.raises(RuntimeError, match="invalid preexisting semantics"):
            command.upgrade(_alembic_cfg(db_url), "head")
    finally:
        engine.dispose()


def test_repo_create_defaults_to_legacy_identity_and_update_preserves_identity(app_session) -> None:
    from core.admin_repo import DietTypesRepo

    with app_session.app_context():
        repo = DietTypesRepo()
        diet_id = repo.create(site_id=None, name="Ny typ", default_select=False)
        created = repo.get_by_id(diet_id)
        assert created is not None
        assert created["semantics"] == "legacy_bucket"
        assert created["requirement_key"] == f"legacy_{diet_id}"

        repo.update(diet_id, name="Ny typ uppdaterad", diet_family="Övrigt")
        updated = repo.get_by_id(diet_id)
        assert updated is not None
        assert updated["requirement_key"] == f"legacy_{diet_id}"
        assert updated["semantics"] == "legacy_bucket"


def test_explicit_atomic_repo_create_uses_opaque_atomic_identity(app_session) -> None:
    from core.admin_repo import DietTypesRepo

    with app_session.app_context():
        repo = DietTypesRepo()
        diet_id = repo.create(site_id=None, name="Atomic typ", default_select=False, semantics="atomic")
        created = repo.get_by_id(diet_id)

        assert created is not None
        assert created["semantics"] == "atomic"
        assert str(created["requirement_key"]).startswith("req_")


def test_rename_preserves_requirement_key(app_session) -> None:
    from core.admin_repo import DietTypesRepo

    with app_session.app_context():
        repo = DietTypesRepo()
        diet_id = repo.create(site_id=None, name="Byt namn", default_select=False)
        before = repo.get_by_id(diet_id)
        assert before is not None

        repo.update(diet_id, name="Bytt namn", diet_family="Övrigt")
        after = repo.get_by_id(diet_id)
        assert after is not None
        assert after["requirement_key"] == before["requirement_key"]
        assert after["name"] == "Bytt namn"


def test_legacy_site_id_null_stays_null_after_identity_upgrade(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "null_site_identity.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            _seed_legacy_dietary_types_table(conn, with_site_id=True)
            conn.execute(text("INSERT INTO dietary_types(id, tenant_id, site_id, name, default_select) VALUES (13, 1, NULL, 'Timbal', 0)"))

        command.stamp(_alembic_cfg(db_url), "0034_add_dietary_types_site_id")
        command.upgrade(_alembic_cfg(db_url), "head")

        with engine.connect() as conn:
            row = conn.execute(text("SELECT site_id, requirement_key, semantics FROM dietary_types WHERE id=13")).fetchone()

        assert row is not None
        assert row[0] is None
        assert row[1] == "legacy_13"
        assert row[2] == "legacy_bucket"
    finally:
        engine.dispose()


def test_tenant_isolation_for_legacy_diet_service_crud(app_session) -> None:
    from core.diet_service import DietService
    from core.db import get_session

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("DELETE FROM unit_diet_assignments"))
            db.execute(text("DELETE FROM dietary_types"))
            db.commit()
        finally:
            db.close()

        service = DietService()
        diet_a = service.create_diet_type(tenant_id=1, name="Diet A", default_select=False)
        diet_b = service.create_diet_type(tenant_id=2, name="Diet B", default_select=True)

        list_a = service.list_diet_types(1)
        assert [row["name"] for row in list_a] == ["Diet A"]
        assert set(list_a[0].keys()) == {"id", "name", "default_select"}

        assert service.update_diet_type(1, diet_b, name="Diet B renamed", default_select=False) is False
        assert service.delete_diet_type(1, diet_b) is False

        assert service.update_diet_type(1, diet_a, name="Diet A renamed", default_select=True) is True
        assert service.delete_diet_type(1, diet_a) is True

        list_b = service.list_diet_types(2)
        assert len(list_b) == 1
        assert list_b[0]["name"] == "Diet B"

        db = get_session()
        try:
            remaining = db.execute(text("SELECT name, default_select FROM dietary_types ORDER BY id")).fetchall()
        finally:
            db.close()

        assert remaining == [("Diet B", 1)]