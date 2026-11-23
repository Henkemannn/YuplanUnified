from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from core.db import get_session
from core.models import Department, Site, Tenant, User


PAGE_ROUTES = (
    "/ui/kitchen/planering?ui=product2&site_id={site_id}",
    "/ui/kitchen/planering/day?ui=product2&site_id={site_id}&date=2026-11-23&meal=lunch",
    "/ui/kitchen/planering/day/production?ui=product2&site_id={site_id}&date=2026-11-23&meal=lunch",
)


def _seed_scope(app_session) -> dict[str, int | str]:
    suffix = uuid.uuid4().hex
    db = get_session()
    try:
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                "UNIQUE(user_id, tenant_id, site_id))"
            )
        )
        tenant_a = Tenant(name=f"SEC-F09 A {suffix}")
        tenant_b = Tenant(name=f"SEC-F09 B {suffix}")
        db.add_all([tenant_a, tenant_b])
        db.flush()
        site_a = Site(id=str(uuid.uuid4()), tenant_id=tenant_a.id, name="SEC-F09 Site A1")
        site_a2 = Site(id=str(uuid.uuid4()), tenant_id=tenant_a.id, name="SEC-F09 Site A2")
        site_b = Site(id=str(uuid.uuid4()), tenant_id=tenant_b.id, name="SEC-F09 Site B1")
        db.add_all([site_a, site_a2, site_b])
        db.flush()
        db.add_all(
            [
                Department(id=str(uuid.uuid4()), site_id=site_a.id, name="SEC-F09 Department A1"),
                Department(id=str(uuid.uuid4()), site_id=site_a2.id, name="SEC-F09 Department A2"),
            ]
        )
        user = User(
            tenant_id=tenant_a.id,
            username=f"sec-f09-{suffix}",
            email=f"sec-f09-{suffix}@example.test",
            password_hash="fixture-only",
            role="admin",
            auth_version=1,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {"user_id": user.id, "tenant_id": tenant_a.id, "site_id": site_a.id},
        )
        db.commit()
        return {
            "user_id": user.id,
            "tenant_a": tenant_a.id,
            "site_a": site_a.id,
            "site_a2": site_a2.id,
            "site_b": site_b.id,
        }
    finally:
        db.close()


def _authenticate(client, scope: dict[str, int | str]) -> None:
    with client.session_transaction() as session:
        session.update(
            {
                "user_id": scope["user_id"],
                "role": "admin",
                "tenant_id": scope["tenant_a"],
                "site_id": scope["site_a"],
                "auth_version": 1,
            }
        )


@pytest.mark.parametrize("route_template", PAGE_ROUTES)
def test_product2_pages_reject_site_switch_and_historical_binding(
    app_session,
    route_template: str,
) -> None:
    scope = _seed_scope(app_session)
    client = app_session.test_client()
    _authenticate(client, scope)

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {
                "user_id": scope["user_id"],
                "tenant_id": scope["tenant_a"],
                "site_id": scope["site_a2"],
            },
        )
        db.commit()
    finally:
        db.close()

    response = client.get(route_template.format(site_id=scope["site_a2"]))

    assert response.status_code in (401, 403)
    assert b"SEC-F09 Site A2" not in response.data


@pytest.mark.parametrize("route_template", PAGE_ROUTES)
def test_product2_pages_reject_other_tenant_and_missing_active_site(
    app_session,
    route_template: str,
) -> None:
    scope = _seed_scope(app_session)
    client = app_session.test_client()
    _authenticate(client, scope)

    response = client.get(route_template.format(site_id=scope["site_b"]))
    assert response.status_code in (401, 403, 404)
    assert b"SEC-F09 Site B1" not in response.data

    with client.session_transaction() as session:
        session.pop("site_id", None)
    response = client.get(route_template.format(site_id=scope["site_a"]))
    assert response.status_code in (401, 403)
    assert b"SEC-F09 Site A1" not in response.data


def test_product2_superuser_keeps_same_tenant_scope(app_session) -> None:
    scope = _seed_scope(app_session)
    db = get_session()
    try:
        user = User(
            tenant_id=scope["tenant_a"],
            username=f"sec-f09-superuser-{uuid.uuid4().hex}",
            email=f"sec-f09-superuser-{uuid.uuid4().hex}@example.test",
            password_hash="fixture-only",
            role="superuser",
            auth_version=1,
            is_active=True,
        )
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    client = app_session.test_client()
    with client.session_transaction() as session:
        session.update(
            {
                "user_id": user_id,
                "role": "superuser",
                "tenant_id": scope["tenant_a"],
                "site_id": scope["site_a"],
                "auth_version": 1,
            }
        )

    response = client.get(PAGE_ROUTES[0].format(site_id=scope["site_a2"]))

    assert response.status_code != 403


def test_product2_page1_uses_active_site_without_query(app_session) -> None:
    scope = _seed_scope(app_session)
    client = app_session.test_client()
    _authenticate(client, scope)

    response = client.get("/ui/kitchen/planering?ui=product2")

    assert response.status_code == 200
    assert b"SEC-F09 Site A1" in response.data


def test_product2_page1_without_active_site_does_not_redirect_to_site_picker(app_session) -> None:
    scope = _seed_scope(app_session)
    client = app_session.test_client()
    _authenticate(client, scope)
    with client.session_transaction() as session:
        session.pop("site_id", None)

    response = client.get("/ui/kitchen/planering?ui=product2")

    assert response.status_code in (401, 403)
    assert response.location is None
    assert b"select_site" not in response.data


def test_product2_request_without_binding_is_denied(app_session) -> None:
    scope = _seed_scope(app_session)
    client = app_session.test_client()
    _authenticate(client, scope)
    db = get_session()
    try:
        db.execute(
            text(
                "DELETE FROM kitchen_user_sites "
                "WHERE user_id = :user_id AND tenant_id = :tenant_id"
            ),
            {"user_id": scope["user_id"], "tenant_id": scope["tenant_a"]},
        )
        db.commit()
    finally:
        db.close()

    response = client.get(PAGE_ROUTES[0].format(site_id=scope["site_a"]))

    assert response.status_code in (401, 403)


@pytest.mark.parametrize("route_template", PAGE_ROUTES)
def test_product2_anonymous_request_is_denied(app_session, route_template: str) -> None:
    scope = _seed_scope(app_session)
    client = app_session.test_client()

    response = client.get(route_template.format(site_id=scope["site_a"]))

    assert response.status_code in (401, 403)
    assert b"SEC-F09 Site A1" not in response.data


def test_product2_unauthorized_role_is_denied(app_session) -> None:
    scope = _seed_scope(app_session)
    client = app_session.test_client()
    _authenticate(client, scope)
    db = get_session()
    try:
        db.execute(
            text("UPDATE users SET role = 'viewer' WHERE id = :user_id"),
            {"user_id": scope["user_id"]},
        )
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as session:
        session["role"] = "viewer"

    response = client.get(PAGE_ROUTES[0].format(site_id=scope["site_a"]))

    assert response.status_code == 403
