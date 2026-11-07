from __future__ import annotations

import uuid

from core.app_factory import create_app
from core.auth_rate_limit import (
    AuthRateLimitDecision,
    AuthRateLimitReservationError,
    AuthRateLimitLease,
)
from core.db import create_all, get_session
from core.models import AuthLoginThrottle, AuthLoginThrottleReservation, Tenant, User
from sqlalchemy import select
from werkzeug.security import generate_password_hash


def _make_app(tmp_path) -> object:
    db_path = tmp_path / "persistent-login.db"
    app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{db_path.as_posix()}",
            "FORCE_DB_REINIT": True,
            "AUTH_RATE_LIMIT": {
                "window_sec": 300,
                "max_failures": 5,
                "lock_sec": 60,
                "ip_max_failures": 100,
            },
        }
    )
    with app.app_context():
        create_all()
    return app


def _seed_user(app, email: str) -> None:
    with app.app_context():
        db = get_session()
        tenant = Tenant(name=f"Login tenant {uuid.uuid4().hex}")
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email=email,
                password_hash=generate_password_hash("correct-password"),
                role="superuser",
            )
        )
        db.commit()
        db.close()


def test_login_uses_persistent_store_and_locks_on_fifth_failure(tmp_path) -> None:
    app = _make_app(tmp_path)
    email = f"persistent-{uuid.uuid4().hex}@example.com"
    _seed_user(app, email)
    client = app.test_client()

    for _ in range(4):
        response = client.post(
            "/auth/login",
            json={"email": email, "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1

    response = client.post(
        "/auth/login",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 429
    assert "access_token" not in (response.get_json() or {})


def test_fifth_failure_finishes_account_and_ip_and_preserves_other_account(
    tmp_path,
) -> None:
    app = _make_app(tmp_path)
    first_email = f"first-{uuid.uuid4().hex}@example.com"
    second_email = f"second-{uuid.uuid4().hex}@example.com"
    _seed_user(app, first_email)
    _seed_user(app, second_email)
    client = app.test_client()

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json={"email": first_email, "password": "wrong-password"},
        )
    assert response.status_code == 429

    with app.app_context():
        db = get_session()
        rows = db.execute(select(AuthLoginThrottle)).scalars().all()
        reservations = db.execute(select(AuthLoginThrottleReservation)).scalars().all()
        assert sorted(row.failure_count for row in rows) == [5, 5]
        assert all(row.in_flight_count == 0 for row in rows)
        assert reservations == []
        db.close()

    with client.session_transaction() as session:
        assert session.get("user_id") is None
    response = client.post(
        "/auth/login",
        json={"email": second_email, "password": "correct-password"},
    )
    assert response.status_code == 200

def test_missing_hmac_secret_returns_503_without_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_SECRET", "")
    app = _make_app(tmp_path)
    app.config["AUTH_RATE_LIMIT_HMAC_SECRET"] = ""
    client = app.test_client()

    response = client.post(
        "/auth/login",
        json={"email": "missing-secret@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.get_json() == {
        "error": "service unavailable",
        "message": "service unavailable",
    }
    with client.session_transaction() as session:
        assert session.get("user_id") is None


def test_unavailable_rate_limit_storage_returns_503(monkeypatch, tmp_path) -> None:
    app = _make_app(tmp_path)

    def unavailable_session():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("core.auth.get_new_session", unavailable_session)
    response = app.test_client().post(
        "/auth/login",
        json={"email": "unavailable@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"


def test_expired_reservation_returns_503_without_authentication(monkeypatch, tmp_path) -> None:
    app = _make_app(tmp_path)

    class ExpiredStore:
        def begin_attempt(self, email: str, ip_address: str):
            return (
                AuthRateLimitDecision(allowed=True),
                AuthRateLimitLease("a" * 64, "b" * 64, True, "expired"),
            )

        def complete_attempt(self, lease, *, success: bool):
            raise AuthRateLimitReservationError("expired")

    monkeypatch.setattr("core.auth._login_rate_limit_store", lambda: ExpiredStore())
    response = app.test_client().post(
        "/auth/login",
        json={"email": "expired@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert "access_token" not in (response.get_json() or {})
