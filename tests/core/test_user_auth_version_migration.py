from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

from core.models import Base, Tenant, User


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_0046_upgrade_backfills_auth_version_and_must_change_password_and_preserves_roundtrip(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "user_auth_version_migration.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "0044_add_department_menu_row_demands")

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants(id, name) VALUES (1, 'Tenant 1')"))
            conn.execute(
                text(
                    "INSERT INTO users (tenant_id, username, email, password_hash, role, is_active) "
                    "VALUES (1, 'legacy.user@example.com', 'legacy.user@example.com', :ph, 'admin', 1)"
                ),
                {"ph": generate_password_hash("OldPassw0rd!")},
            )

        command.upgrade(_alembic_cfg(db_url), "head")

        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("users")}
        assert "auth_version" in columns
        assert "must_change_password" in columns

        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        sess = Session()
        try:
            user = sess.query(User).filter(User.email == "legacy.user@example.com").one()
            assert int(user.auth_version) == 1
            assert user.must_change_password is False

            tenant = sess.query(Tenant).first()
            assert tenant is not None
            fresh = User(
                tenant_id=tenant.id,
                email="fresh.user@example.com",
                username="fresh.user@example.com",
                password_hash=generate_password_hash("FreshPassw0rd!"),
                role="admin",
            )
            sess.add(fresh)
            sess.commit()
            sess.refresh(fresh)
            assert int(fresh.auth_version) == 1
            assert fresh.must_change_password is False
        finally:
            sess.close()

        command.downgrade(_alembic_cfg(db_url), "0044_add_department_menu_row_demands")
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("users")}
        assert "auth_version" not in columns
        assert "must_change_password" not in columns

        command.upgrade(_alembic_cfg(db_url), "head")
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("users")}
        assert "auth_version" in columns
        assert "must_change_password" in columns

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT auth_version, must_change_password FROM users WHERE email='legacy.user@example.com'")
            ).fetchone()
            assert row is not None
            assert int(row[0]) == 1
            assert int(row[1]) == 0
    finally:
        engine.dispose()
