from __future__ import annotations

import pytest

from core.db import get_session
from core.models import Dish, User
from sqlalchemy import text
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash


class _Menu:
    id = 9041


class _MenuService:
    def __init__(self, error: str):
        self.error = error
        self.set_variant_called = False

    def set_variant_atomic(
        self,
        tenant_id,
        site_id,
        week,
        year,
        day,
        meal,
        variant_type,
        dish_id,
        dish_name=None,
    ):
        raise ValueError(self.error)

    def set_variant_atomic_success(self, *args, **kwargs):
        self.set_variant_called = True
        return 9041, 1


def _seed_user_scope(app_session, *, site_id: str, tenant_id: int = 1) -> None:
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites (id, name, tenant_id, version) "
                    "VALUES (:site_id, :name, :tenant_id, 0)"
                ),
                {
                    "site_id": site_id,
                    "name": f"API test {site_id}",
                    "tenant_id": tenant_id,
                },
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, "
                    "tenant_id INTEGER NOT NULL, "
                    "site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text("DELETE FROM kitchen_user_sites WHERE user_id = 9041")
            )
            db.query(User).filter(User.id == 9041).delete(synchronize_session=False)
            db.add(
                User(
                    id=9041,
                    tenant_id=tenant_id,
                    username="menu-api-test",
                    email="menu-api-test@example.test",
                    password_hash="not-used",
                    role="admin",
                    is_active=True,
                    auth_version=1,
                )
            )
            db.flush()
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                    "VALUES (9041, :tenant_id, :site_id)"
                ),
                {"tenant_id": tenant_id, "site_id": site_id},
            )
            db.commit()
        finally:
            db.close()


def _authenticated_client(app_session, site_id: str = "04k-api-site"):
    _seed_user_scope(app_session, site_id=site_id)
    client = app_session.test_client()
    client.environ_base["HTTP_X_USER_ID"] = "9041"
    with client.session_transaction() as session:
        session["tenant_id"] = 1
        session["site_id"] = site_id
        session["role"] = "admin"
        session["user_id"] = 9041
        session["auth_version"] = 1
    return client


def _payload() -> dict[str, object]:
    return {
        "site_id": "04k-api-site",
        "week": 23,
        "year": 2041,
        "day": "monday",
        "meal": "lunch",
        "variant_type": "main",
        "dish_id": 1,
    }


def _write_state(app_session) -> tuple[int, ...]:
    with app_session.app_context():
        db = get_session()
        try:
            tables = (
                "menus",
                "menu_variants",
                "dishes",
                "commun_builder_menu_links",
                "commun_builder_publication_pins",
                "commun_builder_publication_revisions",
            )
            return tuple(
                int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
                for table in tables
            )
        finally:
            db.close()


def _real_login_client(app_session) -> tuple[object, str]:
    with app_session.app_context():
        db = get_session()
        try:
            site_id = "real-login-site-a"
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites (id, name, tenant_id, version) "
                    "VALUES (:site_id, 'Real login site A', 1, 0)"
                ),
                {"site_id": site_id},
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, "
                    "tenant_id INTEGER NOT NULL, "
                    "site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "DELETE FROM kitchen_user_sites WHERE user_id IN "
                    "(SELECT id FROM users WHERE email=:email)"
                ),
                {"email": "real-menu-api-user@example.test"},
            )
            db.query(User).filter(
                User.email == "real-menu-api-user@example.test"
            ).delete(synchronize_session=False)
            db.add(
                User(
                    tenant_id=1,
                    username="real-menu-api-user",
                    email="real-menu-api-user@example.test",
                    password_hash=generate_password_hash("Passw0rd!"),
                    role="admin",
                    is_active=True,
                    auth_version=1,
                )
            )
            db.flush()
            user_id = int(db.query(User).filter(User.email == "real-menu-api-user@example.test").one().id)
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                    "VALUES (:user_id, 1, :site_id)"
                ),
                {"user_id": user_id, "site_id": site_id},
            )
            db.commit()
        finally:
            db.close()

    client = app_session.test_client()
    response = client.post(
        "/auth/login",
        json={"email": "real-menu-api-user@example.test", "password": "Passw0rd!"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, response.get_json()
    with client.session_transaction() as session:
        assert session.get("site_id") == site_id
        assert session.get("site_lock") is True
    return client, site_id


def _revoke_or_move_real_binding(
    app_session, *, site_id: str | None
) -> None:
    with app_session.app_context():
        db = get_session()
        try:
            if site_id is None:
                db.execute(
                    text("DELETE FROM kitchen_user_sites WHERE user_id IN (SELECT id FROM users WHERE email=:email)"),
                    {"email": "real-menu-api-user@example.test"},
                )
            else:
                db.execute(
                    text(
                        "UPDATE kitchen_user_sites SET site_id=:site_id "
                        "WHERE user_id IN (SELECT id FROM users WHERE email=:email)"
                    ),
                    {
                        "site_id": site_id,
                        "email": "real-menu-api-user@example.test",
                    },
                )
            db.commit()
        finally:
            db.close()


def _post_variant_without_headers(client, payload: dict[str, object]):
    return client.post("/menu/variant/set", json=payload)


def test_menu_site_conflict_is_http_409_and_does_not_set_variant(
    app_session, monkeypatch
):
    service = _MenuService("menu_site_conflict: legacy schema")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client = _authenticated_client(app_session)
    before = _write_state(app_session)

    response = client.post(
        "/menu/variant/set",
        json=_payload(),
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "ok": False,
        "error": "menu_site_conflict",
        "status": 409,
    }
    assert service.set_variant_called is False
    assert _write_state(app_session) == before


def test_site_tenant_mismatch_is_fail_closed_without_detail(
    app_session, monkeypatch
):
    service = _MenuService("menu_tenant_mismatch: internal identifiers")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client = _authenticated_client(app_session)
    before = _write_state(app_session)

    response = client.post(
        "/menu/variant/set",
        json=_payload(),
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "ok": False,
        "error": "site_unavailable",
        "status": 403,
    }
    assert service.set_variant_called is False
    assert _write_state(app_session) == before


def test_bound_site_cannot_change_variant_for_another_site(
    app_session, monkeypatch
):
    service = _MenuService("menu_site_conflict: should not be reached")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client = _authenticated_client(app_session, site_id="site-a")
    payload = {**_payload(), "site_id": "site-b"}
    _seed_user_scope(app_session, site_id="site-a")
    with client.session_transaction() as session:
        session["site_id"] = "site-a"
    before = _write_state(app_session)

    response = client.post(
        "/menu/variant/set",
        json=payload,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert response.status_code == 403
    assert service.set_variant_called is False
    assert _write_state(app_session) == before


def test_missing_site_is_rejected_before_menu_resolution(app_session, monkeypatch):
    service = _MenuService("menu_site_conflict: should not be reached")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client = _authenticated_client(app_session, site_id="site-a")
    payload = {key: value for key, value in _payload().items() if key != "site_id"}
    with client.session_transaction() as session:
        session.pop("site_id", None)
    before = _write_state(app_session)

    response = client.post(
        "/menu/variant/set",
        json=payload,
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert response.status_code == 400
    assert response.get_json()["detail"] == "site_id required"
    assert service.set_variant_called is False
    assert _write_state(app_session) == before


def test_null_site_is_rejected_even_with_locked_session_site(
    app_session, monkeypatch
):
    service = _MenuService("menu_site_conflict: should not be reached")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client = _authenticated_client(app_session, site_id="site-a")
    before = _write_state(app_session)

    response = client.post(
        "/menu/variant/set",
        json={**_payload(), "site_id": None},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert response.status_code == 400
    assert response.get_json()["detail"] == "site_id required"
    assert service.set_variant_called is False
    assert _write_state(app_session) == before


def test_bound_site_cannot_target_a_site_in_another_tenant(
    app_session, monkeypatch
):
    service = _MenuService("menu_site_conflict: should not be reached")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client = _authenticated_client(app_session, site_id="site-a")
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites (id, name, tenant_id, version) "
                    "VALUES ('site-tenant-b', 'Tenant B site', 2, 0)"
                )
            )
            db.commit()
        finally:
            db.close()
    before = _write_state(app_session)

    response = client.post(
        "/menu/variant/set",
        json={**_payload(), "site_id": "site-tenant-b"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "ok": False,
        "error": "site_unavailable",
        "status": 403,
    }
    assert service.set_variant_called is False
    assert _write_state(app_session) == before


def test_anonymous_variant_write_is_rejected(app_session):
    client = app_session.test_client()
    response = client.post("/menu/variant/set", json=_payload())

    assert response.status_code == 401


def test_bound_site_can_reach_variant_service(app_session, monkeypatch):
    class _SuccessService:
        def __init__(self):
            self.calls = []

        def set_variant_atomic(self, **kwargs):
            self.calls.append(kwargs)
            return 9041, 7

    service = _SuccessService()
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client = _authenticated_client(app_session, site_id="site-a")

    response = client.post(
        "/menu/variant/set",
        json=_payload() | {"site_id": "site-a"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "menu_id": 9041,
        "menu_variant_id": 7,
    }
    assert service.calls[0]["site_id"] == "site-a"


def test_foreign_tenant_dish_is_rejected_without_writes(app_session):
    client, site_id = _real_login_client(app_session)
    with app_session.app_context():
        db = get_session()
        try:
            foreign_dish = Dish(
                id=9043,
                tenant_id=2,
                name="Foreign tenant dish",
                category=None,
            )
            db.add(foreign_dish)
            db.commit()
        finally:
            db.close()

    before = _write_state(app_session)
    response = _post_variant_without_headers(
        client,
        {**_payload(), "site_id": site_id, "dish_id": 9043},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "dish_tenant_mismatch"
    assert _write_state(app_session) == before


def test_missing_dish_is_rejected_without_writes(app_session):
    client, site_id = _real_login_client(app_session)
    before = _write_state(app_session)

    response = _post_variant_without_headers(
        client,
        {**_payload(), "site_id": site_id, "dish_id": 999999},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "dish_not_found"
    assert _write_state(app_session) == before


def test_database_failure_rolls_back_menu_and_new_dish(app_session):
    client, site_id = _real_login_client(app_session)
    with client.session_transaction() as session:
        tenant_id = int(session["tenant_id"])

    before = _write_state(app_session)

    def fail_before_commit(session):
        raise SQLAlchemyError("forced transaction failure")

    event.listen(Session, "before_commit", fail_before_commit, once=True)
    with app_session.app_context():
        with pytest.raises(SQLAlchemyError, match="forced transaction failure"):
            app_session.menu_service.set_variant_atomic(
                tenant_id=tenant_id,
                site_id=site_id,
                week=23,
                year=2041,
                day="monday",
                meal="lunch",
                variant_type="main",
                dish_id=None,
                dish_name="Rollback dish",
            )

    assert _write_state(app_session) == before


def test_real_login_stale_site_lock_is_rejected_after_binding_revocation(
    app_session, monkeypatch
):
    service = _MenuService("menu_site_conflict: should not be reached")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client, site_id = _real_login_client(app_session)
    _revoke_or_move_real_binding(app_session, site_id=None)
    before = _write_state(app_session)

    response = _post_variant_without_headers(
        client,
        {**_payload(), "site_id": site_id},
    )

    assert response.status_code == 401
    assert response.get_json() is not None
    assert service.set_variant_called is False
    with client.session_transaction() as session:
        assert session.get("user_id") is None
        assert session.get("site_id") is None
    assert _write_state(app_session) == before


def test_real_login_old_site_lock_is_rejected_after_binding_moves(
    app_session, monkeypatch
):
    service = _MenuService("menu_site_conflict: should not be reached")
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client, old_site_id = _real_login_client(app_session)
    new_site_id = "real-login-site-b"
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites (id, name, tenant_id, version) "
                    "VALUES (:site_id, 'Real login site B', 1, 0)"
                ),
                {"site_id": new_site_id},
            )
            db.commit()
        finally:
            db.close()
    _revoke_or_move_real_binding(app_session, site_id=new_site_id)
    before = _write_state(app_session)

    response = _post_variant_without_headers(
        client,
        {**_payload(), "site_id": old_site_id},
    )

    assert response.status_code == 401
    assert response.get_json() is not None
    assert service.set_variant_called is False
    with client.session_transaction() as session:
        assert session.get("user_id") is None
        assert session.get("site_id") is None
    assert _write_state(app_session) == before


def test_real_login_bound_site_remains_allowed(app_session, monkeypatch):
    class _SuccessService:
        def set_variant_atomic(self, **kwargs):
            return 9041, 7

    service = _SuccessService()
    monkeypatch.setattr(app_session, "menu_service", service, raising=False)
    client, site_id = _real_login_client(app_session)

    response = _post_variant_without_headers(
        client,
        {**_payload(), "site_id": site_id},
    )

    assert response.status_code == 200
    assert response.get_json()["menu_variant_id"] == 7
