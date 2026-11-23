import pytest
import time

from flask import g, request, session as flask_session
from sqlalchemy import text

from core.db import get_session
from core.jwt_utils import issue_token_pair
from tests.test_admin_user_target_authorization import _create_user, _login, _seed_scope


def _user_id(app_session, email):
    with app_session.app_context():
        db = get_session()
        try:
            return int(
                db.execute(
                    text("SELECT id FROM users WHERE email=:email"),
                    {"email": email},
                ).scalar_one()
            )
        finally:
            db.close()


def _access_token(app_session, email):
    with app_session.app_context():
        db = get_session()
        try:
            user = db.execute(
                text("SELECT id, auth_version, role, tenant_id FROM users WHERE email=:email"),
                {"email": email},
            ).one()
            token, _, _ = issue_token_pair(
                user_id=int(user.id),
                role=str(user.role),
                tenant_id=int(user.tenant_id),
                auth_version=int(user.auth_version),
                secret=str(app_session.config["JWT_SECRET"]),
            )
            return token, int(user.id)
        finally:
            db.close()


@pytest.mark.parametrize("route", ["/admin/audit", "/ui/admin/users"])
def test_bearer_identity_updates_request_context_for_both_decorators(app_session, route):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")
    token, bearer_user_id = _access_token(app_session, data["admin_a"])
    observed = {}
    with client.session_transaction() as session:
        session["site_id"] = data["site_a"]

    def observe_identity(response):
        observed["g_user_id"] = getattr(g, "user_id", None)
        return response

    callbacks = app_session.after_request_funcs.setdefault(None, [])
    callbacks.append(observe_identity)
    try:
        response = client.get(route, headers={"Authorization": f"Bearer {token}"})
    finally:
        callbacks.remove(observe_identity)

    assert response.status_code == 200
    assert observed["g_user_id"] == bearer_user_id
    with client.session_transaction() as session:
        assert session["user_id"] == bearer_user_id
        assert session["authenticated_user_id"] == bearer_user_id


def _switch_site(client, site_id, tenant_id):
    response = client.post(
        f"/ui/systemadmin/switch-site/{site_id}",
        data={"tenant_id": str(tenant_id)},
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_real_superuser_support_keeps_effective_context_separate(app_session):
    data = _seed_scope(app_session)
    _create_user(
        app_session,
        tenant_id=data["tenant_b"],
        email="08b03b-tenant-b-user@example.com",
        role="staff",
        site_id=data["site_b"],
    )
    superuser_id = _user_id(app_session, data["superuser"])
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")

    _switch_site(client, data["site_a"], data["tenant_a"])
    _switch_site(client, data["site_b"], data["tenant_b"])

    response = client.get("/ui/admin/users")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "08b03b-tenant-b-user@example.com" in html
    assert data["admin_a"] not in html

    with client.session_transaction() as session:
        assert session["tenant_id"] == data["tenant_b"]
        assert session["site_id"] == data["site_b"]
        assert session["authenticated_tenant_id"] == data["tenant_a"]
        assert session["authenticated_user_id"] == superuser_id
        assert session["role"] == "superuser"


def test_real_superuser_stop_restores_system_context_and_site(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")
    _switch_site(client, data["site_b"], data["tenant_b"])

    response = client.post("/superuser/impersonate/stop", follow_redirects=False)
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["tenant_id"] == data["tenant_a"]
        assert session["authenticated_tenant_id"] == data["tenant_a"]
        assert "site_id" not in session
        assert "impersonate" not in session


def test_real_superuser_expiry_clears_effective_context(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")
    _switch_site(client, data["site_b"], data["tenant_b"])
    with client.session_transaction() as session:
        state = dict(session["impersonate"])
        state["expires_at"] = int(time.time()) - 1
        session["impersonate"] = state

    response = client.get("/ui/admin/users")
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["tenant_id"] == data["tenant_a"]
        assert "site_id" not in session
        assert "impersonate" not in session


def test_stop_and_expiry_restore_roles_for_next_request(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")
    with client.session_transaction() as session:
        assert session.get("roles") in (None, ["superuser"])

    _switch_site(client, data["site_b"], data["tenant_b"])
    assert client.get("/ui/admin/users").status_code == 200
    with client.session_transaction() as session:
        assert "admin" in session["roles"]
    assert client.post("/superuser/impersonate/stop").status_code == 200
    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]
    assert client.get("/ui/admin/users").status_code == 200
    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]

    _switch_site(client, data["site_b"], data["tenant_b"])
    with client.session_transaction() as session:
        state = dict(session["impersonate"])
        state["expires_at"] = int(time.time()) - 1
        session["impersonate"] = state
    assert client.get("/ui/admin/users").status_code == 200
    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]
        assert "impersonate" not in session


def test_switching_support_context_does_not_snapshot_temporary_admin_role(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")

    _switch_site(client, data["site_a"], data["tenant_a"])
    assert client.get("/ui/admin/users").status_code == 200
    _switch_site(client, data["site_b"], data["tenant_b"])
    assert client.post("/superuser/impersonate/stop").status_code == 200

    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]
    assert client.get("/ui/admin/users").status_code == 200
    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]


def test_switching_support_context_does_not_leak_role_on_expiry(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")

    _switch_site(client, data["site_a"], data["tenant_a"])
    assert client.get("/ui/admin/users").status_code == 200
    _switch_site(client, data["site_b"], data["tenant_b"])
    with client.session_transaction() as session:
        state = dict(session["impersonate"])
        state["expires_at"] = int(time.time()) - 1
        session["impersonate"] = state

    assert client.get("/ui/admin/users").status_code == 200
    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]
    assert client.get("/ui/admin/users").status_code == 200
    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]


def test_switching_back_to_original_site_does_not_leak_role_on_stop(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")

    _switch_site(client, data["site_a"], data["tenant_a"])
    assert client.get("/ui/admin/users").status_code == 200
    _switch_site(client, data["site_b"], data["tenant_b"])
    assert client.get("/ui/admin/users").status_code == 200
    _switch_site(client, data["site_a"], data["tenant_a"])
    assert client.post("/superuser/impersonate/stop").status_code == 200

    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]
    assert client.get("/ui/admin/users").status_code == 200
    with client.session_transaction() as session:
        assert session.get("roles") == ["superuser"]


@pytest.mark.parametrize("route", ["/admin/audit", "/ui/admin/users"])
def test_bearer_rejects_stale_session_impersonation(app_session, route):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")
    _switch_site(client, data["site_b"], data["tenant_b"])
    token, other_user_id = _access_token(app_session, data["admin_a"])

    response = client.get(
        route,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (401, 403)
    with client.session_transaction() as session:
        assert "impersonate" not in session
        assert session["tenant_id"] == data["tenant_a"]
        assert session["user_id"] == other_user_id
        assert session["authenticated_user_id"] == other_user_id


@pytest.mark.parametrize("route", ["/admin/audit", "/ui/admin/users"])
@pytest.mark.parametrize("header", ["Bearer", "Bearer ", "Bearer malformed"])
def test_invalid_bearer_never_falls_back_to_valid_session(app_session, route, header):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    superuser_id = _user_id(app_session, data["superuser"])
    _login(client, data["superuser"], password="SuperPassw0rd!2026")

    response = client.get(route, headers={"Authorization": header})

    assert response.status_code == 401
    with client.session_transaction() as session:
        assert session["user_id"] == superuser_id
        assert session["role"] == "superuser"


def test_real_superuser_invalid_site_tenant_pair_is_denied(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["superuser"], password="SuperPassw0rd!2026")
    _switch_site(client, data["site_b"], data["tenant_b"])
    with client.session_transaction() as session:
        session["site_id"] = data["site_a"]

    response = client.get("/ui/admin/users")
    assert response.status_code == 403
    with client.session_transaction() as session:
        assert session["tenant_id"] == data["tenant_b"]
        assert session["site_id"] == data["site_a"]
        assert "impersonate" in session


def test_real_local_admin_cannot_start_or_reuse_impersonation(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["admin_a"])

    response = client.post(
        "/superuser/impersonate/start",
        json={"tenant_id": data["tenant_b"], "reason": "unauthorized"},
    )
    assert response.status_code == 403
    with client.session_transaction() as session:
        session["impersonate"] = {
            "tenant_id": data["tenant_b"],
            "reason": "forged",
            "started_at": int(time.time()),
            "expires_at": int(time.time()) + 900,
            "admin_user_id": 999999,
            "admin_roles": ["superuser"],
        }
    response = client.get("/ui/admin/users")
    assert response.status_code == 403
    with client.session_transaction() as session:
        assert session["tenant_id"] == data["tenant_a"]
        assert "site_id" not in session


@pytest.mark.parametrize(
    "route",
    [
        "/ui/admin/users",
        "/api/reports/weekview?year=2026&week=1",
    ],
)
def test_local_admin_cannot_use_manipulated_other_tenant_context(app_session, route):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data["admin_a"])
    admin_id = _user_id(app_session, data["admin_a"])

    with client.session_transaction() as session:
        session["site_id"] = data["site_a"]

    def tamper_effective_tenant():
        if request.path == route.split("?", 1)[0]:
            flask_session["tenant_id"] = data["tenant_b"]
            flask_session["site_id"] = data["site_a"]

    callbacks = app_session.before_request_funcs.setdefault(None, [])
    callbacks.append(tamper_effective_tenant)
    try:
        response = client.get(route)
    finally:
        callbacks.remove(tamper_effective_tenant)

    assert response.status_code in (401, 403)
    with app_session.app_context():
        db = get_session()
        try:
            binding = db.execute(
                text(
                    "SELECT tenant_id, site_id FROM kitchen_user_sites "
                    "WHERE user_id=:user_id"
                ),
                {"user_id": admin_id},
            ).one()
        finally:
            db.close()
    assert tuple(binding) == (data["tenant_a"], data["site_a"])
    with client.session_transaction() as session:
        assert session.get("authenticated_tenant_id") == data["tenant_a"]
        assert "impersonate" not in session


def test_local_cook_cannot_use_superuser_support_exception(app_session):
    data = _seed_scope(app_session)
    cook_email = "08b-cook-cross-tenant@example.com"
    _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email=cook_email,
        role="cook",
        site_id=data["site_a"],
    )
    client = app_session.test_client()
    _login(client, cook_email, password="TargetPassw0rd!2026")

    with client.session_transaction() as session:
        session["tenant_id"] = data["tenant_b"]
        session["site_id"] = data["site_b"]
        session["impersonate"] = {
            "tenant_id": data["tenant_b"],
            "reason": "forged",
            "started_at": int(time.time()),
            "expires_at": int(time.time()) + 900,
            "admin_user_id": session["user_id"],
            "admin_roles": ["superuser"],
        }

    response = client.get("/api/reports/weekview?year=2026&week=1")

    assert response.status_code in (401, 403)
    with client.session_transaction() as session:
        assert "impersonate" not in session
