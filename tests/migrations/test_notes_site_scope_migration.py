from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[2]


def _config(target: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{target}")
    return config


def test_notes_site_migration_preserves_legacy_rows_and_supports_downgrade(
    tmp_path, monkeypatch
):
    target = tmp_path / "notes-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _config(target)
    command.upgrade(config, "0051_add_site_scoped_menu_uniqueness")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO tenants(id, name, active) VALUES (9701, 'Notes Tenant', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO users(id, tenant_id, email, password_hash, role) "
                    "VALUES (9701, 9701, 'notes@example.test', 'hash', 'admin')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id) "
                    "VALUES ('notes-site', 'Notes Site', 9701)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO notes(tenant_id, user_id, content, private_flag) "
                    "VALUES (9701, 9701, 'legacy', 0)"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "0052_add_site_id_to_notes")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            row = connection.execute(
                text("SELECT content, site_id FROM notes")
            ).one()
            assert row == ("legacy", None)
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            assert connection.execute(
                text("SELECT content, site_id FROM notes")
            ).one() == ("legacy", None)
    finally:
        engine.dispose()

    command.downgrade(config, "0051_add_site_scoped_menu_uniqueness")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" not in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            assert connection.execute(
                text("SELECT content FROM notes")
            ).scalar_one() == "legacy"
    finally:
        engine.dispose()
