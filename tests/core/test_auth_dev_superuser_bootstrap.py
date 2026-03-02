import os

from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import create_all, get_session, init_engine
from core.auth import ensure_dev_sync_superuser_from_env
from core.models import Tenant, User


def _setup_app():
    app = create_app({"TESTING": False, "database_url": "sqlite:///:memory:", "SECRET_KEY": "x" * 64})
    with app.app_context():
        init_engine(app.config.get("SQLALCHEMY_DATABASE_URI"), force=True)
        create_all()
    return app


def test_dev_superuser_bootstrap_creates_user_when_missing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("YUPLAN_DEV_SYNC_SUPERUSER", "1")
    monkeypatch.setenv("SUPERUSER_EMAIL", "root@example.com")
    monkeypatch.setenv("SUPERUSER_PASSWORD", "SuperSecret123!")

    app = _setup_app()
    with app.app_context():
        db = get_session()
        try:
            tenant = Tenant(name="Primary")
            db.add(tenant)
            db.commit()
        finally:
            db.close()

        ensure_dev_sync_superuser_from_env()
        db = get_session()
        try:
            user = db.query(User).filter(User.email == "root@example.com").first()
            assert user is not None
            assert user.role == "superuser"
        finally:
            db.close()


def test_dev_superuser_bootstrap_does_not_overwrite_password(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("YUPLAN_DEV_SYNC_SUPERUSER", "1")
    monkeypatch.setenv("SUPERUSER_EMAIL", "root@example.com")
    monkeypatch.setenv("SUPERUSER_PASSWORD", "SuperSecret123!")

    app = _setup_app()
    with app.app_context():
        db = get_session()
        try:
            tenant = Tenant(name="Primary")
            db.add(tenant)
            db.flush()
            existing_hash = generate_password_hash("ExistingPass123!")
            user = User(
                tenant_id=tenant.id,
                email="root@example.com",
                username="root@example.com",
                password_hash=existing_hash,
                role="superuser",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        ensure_dev_sync_superuser_from_env()
        db = get_session()
        try:
            user = db.query(User).filter(User.email == "root@example.com").first()
            assert user is not None
            assert user.password_hash == existing_hash
        finally:
            db.close()
