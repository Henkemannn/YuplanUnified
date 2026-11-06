from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from alembic import command
from alembic.config import Config
import pytest
from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import PasswordResetToken, Tenant, User
from sqlalchemy import create_engine, inspect, select
from werkzeug.security import check_password_hash, generate_password_hash


def _make_app(tmp_path, mailer):
    app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{(tmp_path / 'password-reset.db').as_posix()}",
            "FORCE_DB_REINIT": True,
            "PASSWORD_RESET_MAILER": mailer,
            "PASSWORD_RESET_PUBLIC_BASE_URL": "https://pilot.example.test",
            "PASSWORD_RESET_HMAC_SECRET": "isolated-password-reset-secret",
        }
    )
    with app.app_context():
        create_all()
    return app


def _seed_user(app, password="old-password", must_change_password=True):
    with app.app_context():
        db = get_session()
        tenant = Tenant(name=f"Reset tenant {uuid.uuid4().hex}")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"reset-{uuid.uuid4().hex}@example.com",
            password_hash=generate_password_hash(password),
            role="superuser",
            refresh_token_jti="old-refresh-jti",
            must_change_password=must_change_password,
        )
        db.add(user)
        db.commit()
        result = (user.email, user.id, user.auth_version)
        db.close()
        return result


def test_reset_request_is_neutral_and_sends_only_for_active_known_account(tmp_path):
    sent = []
    app = _make_app(tmp_path, lambda recipient, url: sent.append((recipient, url)))
    email, _, _ = _seed_user(app)
    client = app.test_client()

    known = client.post("/auth/forgot", json={"email": email})
    unknown = client.post("/auth/forgot", json={"email": "unknown@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.get_json()["message"] == unknown.get_json()["message"]
    assert len(sent) == 1
    assert email in sent[0][0]
    assert "token=" in sent[0][1]
    assert known.headers["Cache-Control"].startswith("no-store")
    assert known.headers["Referrer-Policy"] == "no-referrer"


def test_reset_is_single_use_and_invalidates_old_auth_state(tmp_path):
    sent = []
    app = _make_app(tmp_path, lambda recipient, url: sent.append(url))
    email, user_id, old_version = _seed_user(app)
    client = app.test_client()

    client.post("/auth/forgot", json={"email": email})
    token = sent[0].split("token=", 1)[1]
    response = client.post(
        "/auth/reset",
        json={"token": token, "new_password": "new-password", "confirm_password": "new-password"},
    )
    assert response.status_code == 200

    with app.app_context():
        db = get_session()
        user = db.get(User, user_id)
        assert user is not None
        assert user.auth_version == old_version + 1
        assert user.refresh_token_jti is None
        assert user.must_change_password is False
        assert check_password_hash(user.password_hash, "new-password")
        reset = db.execute(select(PasswordResetToken)).scalar_one()
        assert reset.used_at is not None
        db.close()

    replay = client.post(
        "/auth/reset",
        json={"token": token, "new_password": "third-password", "confirm_password": "third-password"},
    )
    assert replay.status_code == 400


def test_reset_invalidates_existing_login_tokens_and_accepts_only_new_password(tmp_path):
    sent = []
    app = _make_app(tmp_path, lambda recipient, url: sent.append(url))
    email, _, _ = _seed_user(
        app,
        password="old-password",
        must_change_password=False,
    )
    old_client = app.test_client()

    login = old_client.post("/auth/login", json={"email": email, "password": "old-password"})
    assert login.status_code == 200
    tokens = login.get_json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    old_session_cookie = old_client.get_cookie("session")
    assert old_session_cookie is not None
    assert old_client.get("/auth/me").status_code == 200

    reset_client = app.test_client()
    reset_client.post("/auth/forgot", json={"email": email})
    token = parse_qs(urlsplit(sent[0]).query)["token"][0]
    reset = reset_client.post(
        "/auth/reset",
        json={"token": token, "new_password": "new-password", "confirm_password": "new-password"},
    )
    assert reset.status_code == 200

    assert old_client.get_cookie("session").value == old_session_cookie.value
    old_session = old_client.get("/auth/me")
    old_access = old_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    old_refresh = old_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    old_login = old_client.post("/auth/login", json={"email": email, "password": "old-password"})
    new_login = reset_client.post("/auth/login", json={"email": email, "password": "new-password"})
    new_access = reset_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_login.get_json()['access_token']}"},
    )
    assert old_session.status_code == 401
    assert old_access.status_code == 401
    assert old_refresh.status_code == 401
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert new_access.status_code == 200


def test_two_concurrent_reset_posts_claim_token_exactly_once(tmp_path):
    sent = []
    app = _make_app(tmp_path, lambda recipient, url: sent.append(url))
    email, _, _ = _seed_user(app)
    app.test_client().post("/auth/forgot", json={"email": email})
    token = parse_qs(urlsplit(sent[0]).query)["token"][0]
    def consume(password):
        with app.app_context():
            response = app.test_client().post(
                "/auth/reset",
                json={
                    "token": token,
                    "new_password": password,
                    "confirm_password": password,
                },
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(consume, ("first-new-password", "second-new-password")))

    assert results.count(200) == 1
    assert results.count(400) == 1
    with app.app_context():
        db = get_session()
        reset = db.execute(select(PasswordResetToken)).scalar_one()
        assert reset.used_at is not None
        db.close()


def test_reset_delivery_failure_does_not_leave_usable_token(tmp_path, caplog):
    def failing_mailer(recipient, url):
        raise RuntimeError("provider unavailable")

    app = _make_app(tmp_path, failing_mailer)
    email, _, _ = _seed_user(app)
    response = app.test_client().post("/auth/forgot", json={"email": email})

    assert response.status_code == 202
    assert "token=" not in response.get_data(as_text=True)
    assert all("token=" not in record.getMessage() for record in caplog.records)
    with app.app_context():
        db = get_session()
        reset = db.execute(select(PasswordResetToken)).scalar_one()
        assert reset.revoked_at is not None
        db.close()


def test_reset_neutrality_without_mailer_and_for_inactive_accounts(tmp_path):
    app = _make_app(tmp_path, None)
    active_email, _, _ = _seed_user(app)
    with app.app_context():
        db = get_session()
        inactive = User(
            tenant_id=db.query(Tenant).first().id,
            email=f"inactive-{uuid.uuid4().hex}@example.com",
            password_hash=generate_password_hash("old-password"),
            role="superuser",
            is_active=False,
        )
        db.add(inactive)
        db.commit()
        inactive_email = inactive.email
        db.close()

    responses = [
        app.test_client().post("/auth/forgot", json={"email": active_email}),
        app.test_client().post("/auth/forgot", json={"email": inactive_email}),
        app.test_client().post("/auth/forgot", json={"email": "unknown@example.com"}),
    ]
    assert {response.status_code for response in responses} == {202}
    assert {response.get_json()["message"] for response in responses} == {
        responses[0].get_json()["message"]
    }
    with app.app_context():
        db = get_session()
        assert db.query(PasswordResetToken).count() == 0
        db.close()


def test_reset_posts_require_csrf_in_production_like_runtime(tmp_path, monkeypatch):
    sent = []
    app = create_app(
        {
            "TESTING": False,
            "SECRET_KEY": "production-like-secret",
            "JWT_SECRET": "production-like-jwt-secret-0123456789012345",
            "database_url": f"sqlite:///{(tmp_path / 'csrf-reset.db').as_posix()}",
            "FORCE_DB_REINIT": True,
            "PASSWORD_RESET_MAILER": lambda recipient, url: sent.append(url),
            "PASSWORD_RESET_PUBLIC_BASE_URL": "https://pilot.example.test",
            "PASSWORD_RESET_HMAC_SECRET": "isolated-password-reset-secret",
        }
    )
    with app.app_context():
        create_all()
    email, _, _ = _seed_user(app)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    client = app.test_client()
    client.get("/auth/forgot")
    missing_forgot = client.post("/auth/forgot", json={"email": "unknown@example.com"})
    missing_reset = client.post(
        "/auth/reset",
        json={"token": "invalid", "new_password": "new-password", "confirm_password": "new-password"},
    )
    assert missing_forgot.status_code == 403
    assert missing_reset.status_code == 403

    csrf_cookie = client.get_cookie("csrf_token")
    assert csrf_cookie is not None
    csrf_headers = {"X-CSRF-Token": csrf_cookie.value}
    accepted_forgot = client.post(
        "/auth/forgot",
        json={"email": email},
        headers=csrf_headers,
    )
    assert accepted_forgot.status_code == 202
    token = parse_qs(urlsplit(sent[0]).query)["token"][0]
    accepted_reset = client.post(
        "/auth/reset",
        json={
            "token": token,
            "new_password": "new-password",
            "confirm_password": "new-password",
        },
        headers=csrf_headers,
    )
    assert accepted_reset.status_code == 200


def test_reset_requests_are_persistently_throttled_by_account(tmp_path):
    sent = []
    app = _make_app(tmp_path, lambda recipient, url: sent.append(url))
    email, _, _ = _seed_user(app)
    client = app.test_client()

    for _ in range(4):
        response = client.post("/auth/forgot", json={"email": email})
        assert response.status_code == 202
    assert len(sent) == 3

    with app.app_context():
        db = get_session()
        assert db.query(PasswordResetToken).count() == 3
        db.close()


def test_password_reset_migration_round_trips_in_isolated_database(tmp_path, monkeypatch):
    db_url = f"sqlite:///{(tmp_path / 'password-reset-migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "0049_add_auth_login_throttle_reservations")
    command.upgrade(config, "head")
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        assert "password_reset_tokens" in inspector.get_table_names()
        assert "password_reset_throttles" in inspector.get_table_names()
        command.downgrade(config, "0049_add_auth_login_throttle_reservations")
        inspector = inspect(engine)
        assert "password_reset_tokens" not in inspector.get_table_names()
        assert "password_reset_throttles" not in inspector.get_table_names()
    finally:
        engine.dispose()
