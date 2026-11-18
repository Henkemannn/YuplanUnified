from __future__ import annotations

import pytest
import uuid
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.admin_repo import SitesRepo
from core.db import get_session
from core.impersonation import start_impersonation
from core.models import Tenant, User


def _seed_users_and_sites(app):
    suffix = uuid.uuid4().hex[:10]
    superuser_email = f"gate08a-fix-superuser-{suffix}@example.com"
    admin_email = f"gate08a-fix-admin-{suffix}@example.com"
    with app.app_context():
        db = get_session()
        try:
            superuser = User(
                tenant_id=1,
                email=superuser_email,
                username=f"gate08a-fix-superuser-{suffix}",
                password_hash=generate_password_hash("SuperPassw0rd!"),
                role="superuser",
                is_active=True,
                auth_version=1,
            )
            tenant_a = Tenant(name=f"Gate 08A Fix Tenant A {suffix}")
            tenant_b = Tenant(name=f"Gate 08A Fix Tenant B {suffix}")
            db.add_all([superuser, tenant_a, tenant_b])
            db.commit()
            superuser_id = int(superuser.id)
            tenant_a_id = int(tenant_a.id)
            tenant_b_id = int(tenant_b.id)

            sites = {}
            for tenant_id, name in (
                (tenant_a_id, f"Gate 08A Fix Site A1 {suffix}"),
                (tenant_a_id, f"Gate 08A Fix Site A2 {suffix}"),
                (tenant_b_id, f"Gate 08A Fix Site B1 {suffix}"),
            ):
                site, _ = SitesRepo().create_site(name, tenant_id=tenant_id)
                sites[name.split(f" {suffix}")[0]] = str(site["id"])

            admin = User(
                tenant_id=tenant_a_id,
                email=admin_email,
                username=f"gate08a-fix-admin-{suffix}",
                password_hash=generate_password_hash("AdminPassw0rd!"),
                role="admin",
                is_active=True,
                auth_version=1,
            )
            db.add(admin)
            db.flush()
            admin_id = int(admin.id)
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                    "VALUES (:user_id, :tenant_id, :site_id)"
                ),
                {"user_id": admin_id, "tenant_id": tenant_a_id, "site_id": sites["Gate 08A Fix Site A1"]},
            )
            db.commit()
            return {
                "superuser_id": superuser_id,
                "tenant_a": tenant_a_id,
                "tenant_b": tenant_b_id,
                "site_a1": sites["Gate 08A Fix Site A1"],
                "site_a2": sites["Gate 08A Fix Site A2"],
                "site_b1": sites["Gate 08A Fix Site B1"],
                "superuser_email": superuser_email,
                "admin_email": admin_email,
            }
        finally:
            db.close()


def _login(client, email, password):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, response.get_json()


def _state(client):
    with client.session_transaction() as session:
        return {
            "tenant_id": session.get("tenant_id"),
            "site_id": session.get("site_id"),
            "site_lock": session.get("site_lock"),
            "impersonate": session.get("impersonate"),
            "role": session.get("role"),
        }


@pytest.mark.parametrize("route_prefix", ["/ui/systemadmin/switch-site", "/ui/systemadmin/switch-site-core"])
@pytest.mark.parametrize("target_key", ["site_a1", "site_a2", "site_b1"])
def test_site_bound_admin_is_denied_without_session_changes(app_session, route_prefix, target_key):
    data = _seed_users_and_sites(app_session)
    client = app_session.test_client()
    _login(client, data["admin_email"], "AdminPassw0rd!")
    before = _state(client)

    response = client.post(
        f"{route_prefix}/{data[target_key]}",
        data={"tenant_id": data["tenant_a"]},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert _state(client) == before


def test_start_impersonation_rejects_admin_before_state_changes(app_session):
    data = _seed_users_and_sites(app_session)
    with app_session.test_request_context("/"):
        from flask import session

        session.update(
            {
                "role": "admin",
                "user_id": 42,
                "tenant_id": data["tenant_a"],
                "site_id": data["site_a1"],
                "site_lock": True,
            }
        )
        before = dict(session)

        with pytest.raises(PermissionError, match="superuser_required"):
            start_impersonation(data["tenant_b"], "test")

        assert dict(session) == before
        assert "impersonate" not in session


def test_superuser_can_switch_and_stop_impersonation(app_session):
    data = _seed_users_and_sites(app_session)
    client = app_session.test_client()
    _login(client, data["superuser_email"], "SuperPassw0rd!")

    switch = client.post(
        f"/ui/systemadmin/switch-site/{data['site_b1']}",
        data={"tenant_id": data["tenant_b"]},
        follow_redirects=False,
    )
    assert switch.status_code == 302
    switched = _state(client)
    assert switched["tenant_id"] == data["tenant_b"]
    assert switched["site_id"] == data["site_b1"]
    assert switched["site_lock"] is None
    assert switched["impersonate"]["tenant_id"] == data["tenant_b"]

    stop = client.post("/superuser/impersonate/stop")
    assert stop.status_code == 200
    assert _state(client)["impersonate"] is None


@pytest.mark.parametrize("route_prefix", ["/ui/systemadmin/switch-site", "/ui/systemadmin/switch-site-core"])
def test_systemadmin_get_switch_does_not_change_session(app_session, route_prefix):
    data = _seed_users_and_sites(app_session)
    client = app_session.test_client()
    _login(client, data["superuser_email"], "SuperPassw0rd!")
    before = _state(client)

    response = client.get(f"{route_prefix}/{data['site_b1']}", follow_redirects=False)

    # The application intentionally maps method-not-allowed responses to 404.
    assert response.status_code == 404
    assert _state(client) == before


def test_superuser_switch_rejects_site_tenant_mismatch_without_state_change(app_session):
    data = _seed_users_and_sites(app_session)
    client = app_session.test_client()
    _login(client, data["superuser_email"], "SuperPassw0rd!")
    before = _state(client)

    response = client.post(
        f"/ui/systemadmin/switch-site/{data['site_b1']}",
        data={"tenant_id": data["tenant_a"]},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert _state(client) == before


def test_systemadmin_sites_page_uses_post_switch_form(app_session):
    data = _seed_users_and_sites(app_session)
    client = app_session.test_client()
    _login(client, data["superuser_email"], "SuperPassw0rd!")

    response = client.get(f"/ui/systemadmin/customers/{data['tenant_b']}/sites")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'action="/ui/systemadmin/switch-site/{data["site_b1"]}"' in html
    assert 'method="post"' in html
    assert f'name="tenant_id" value="{data["tenant_b"]}"' in html
    assert 'href="/ui/systemadmin/switch-site/' not in html


def test_systemadmin_switch_requires_csrf_when_strict_csrf_is_enabled(app_session):
    data = _seed_users_and_sites(app_session)
    client = app_session.test_client()
    _login(client, data["superuser_email"], "SuperPassw0rd!")
    before = _state(client)
    app_session.config["STRICT_CSRF_IN_TESTS"] = True
    try:
        missing = client.post(
            f"/ui/systemadmin/switch-site/{data['site_b1']}",
            data={"tenant_id": data["tenant_b"]},
            follow_redirects=False,
        )
        assert missing.status_code == 403
        assert _state(client) == before

        invalid = client.post(
            f"/ui/systemadmin/switch-site/{data['site_b1']}",
            data={"tenant_id": data["tenant_b"], "csrf_token": "wrong-token"},
            follow_redirects=False,
        )
        assert invalid.status_code == 403
        assert _state(client) == before

        with client.session_transaction() as session:
            session["CSRF_TOKEN"] = "gate08a-csrf-token"
        valid = client.post(
            f"/ui/systemadmin/switch-site/{data['site_b1']}",
            data={"tenant_id": data["tenant_b"], "csrf_token": "gate08a-csrf-token"},
            follow_redirects=False,
        )
        assert valid.status_code == 302
        assert _state(client)["site_id"] == data["site_b1"]
    finally:
        app_session.config["STRICT_CSRF_IN_TESTS"] = False


def test_real_admin_login_keeps_site_lock(app_session):
    data = _seed_users_and_sites(app_session)
    client = app_session.test_client()
    _login(client, data["admin_email"], "AdminPassw0rd!")

    state = _state(client)
    assert state["role"] == "admin"
    assert state["tenant_id"] == data["tenant_a"]
    assert state["site_id"] == data["site_a1"]
    assert state["site_lock"] is True
    assert state["impersonate"] is None
