import logging
import uuid

import pytest
from sqlalchemy import text

from core.db import get_session
from core.jwt_utils import issue_token_pair
from core.logging_setup import LOG_BUFFER
from tests.test_admin_user_target_authorization import _create_user, _login, _seed_scope


@pytest.fixture
def ensure_warning(client):
    # Trigger a warning log with request context
    logging.getLogger(__name__).warning("pilot warning test")


@pytest.fixture(autouse=True)
def preserve_log_buffer():
    snapshot = list(LOG_BUFFER)
    try:
        yield
    finally:
        LOG_BUFFER.clear()
        LOG_BUFFER.extend(snapshot)


@pytest.fixture
def support_log(app_session):
    request_id = f"f12-support-{uuid.uuid4().hex}"
    LOG_BUFFER.clear()
    try:
        client = app_session.test_client()
        response = client.post(
            "/admin/support/",
            headers={"X-Request-Id": request_id},
        )
        assert response.status_code == 404
        yield request_id
    finally:
        LOG_BUFFER.clear()


def test_support_requires_admin(client_user):
    r = client_user.get("/admin/support/", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert r.status_code in (401, 403)


def test_support_superuser_ok(client_superuser, ensure_warning):
    r = client_superuser.get(
        "/admin/support/", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"}
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "service_version" in data
    assert "events" in data


def test_support_lookup_superuser(client_superuser, ensure_warning):
    client_superuser.get(
        "/admin/support/", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"}
    )
    home = client_superuser.get(
        "/admin/support/", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"}
    ).get_json()
    recents = home.get("recent_warnings", [])
    if recents:
        rid = recents[-1].get("request_id")
        lr = client_superuser.get(
            f"/admin/support/lookup?request_id={rid}",
            headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"},
        )
        assert lr.status_code == 200
        payload = lr.get_json()
        assert payload["request_id"] == rid
    else:
        pytest.skip("No warnings captured; skipping lookup validation")


def test_support_real_identity_matrix_and_positive_lookup(app_session, support_log):
    data = _seed_scope(app_session)
    anonymous = app_session.test_client()
    anonymous_routes = [
        "/admin/support/",
        "/admin/support/lookup?request_id=missing",
        "/admin/support/ticket/missing",
        "/admin/support/ui",
    ]
    assert [anonymous.get(route).status_code for route in anonymous_routes] == [401] * 4

    suffix = uuid.uuid4().hex
    cook_email = f"f12-cook-{suffix}@example.com"
    department_email = f"f12-unit-portal-{suffix}@example.com"
    department_id = f"f12-department-{suffix}"
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS departments("
                    "id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT, "
                    "resident_count_mode TEXT NOT NULL DEFAULT 'manual')"
                )
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name) "
                    "VALUES(:id, :site_id, :name)"
                ),
                {"id": department_id, "site_id": data["site_a"], "name": "F12 Unit"},
            )
            db.commit()
        finally:
            db.close()
    _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email=cook_email,
        role="cook",
        site_id=data["site_a"],
    )
    _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email=department_email,
        role="unit_portal",
        site_id=data["site_a"],
        department_id=department_id,
    )
    identities = {
        "cook": (cook_email, "TargetPassw0rd!2026", 403),
        "unit_portal": (department_email, "TargetPassw0rd!2026", 403),
        "admin_a": (data["admin_a"], "AdminPassw0rd!2026", 403),
        "admin_b": (data["admin_b"], "AdminPassw0rd!2026", 403),
        "superuser": (data["superuser"], "SuperPassw0rd!2026", (200, 200, 200, 200)),
    }
    identity_scopes = {
        "cook": (data["tenant_a"], data["site_a"]),
        "unit_portal": (data["tenant_a"], data["site_a"]),
        "admin_a": (data["tenant_a"], data["site_a"]),
        "admin_b": (data["tenant_b"], data["site_b"]),
        "superuser": (data["tenant_a"], data["site_a"]),
    }
    request_id = support_log
    routes = [
        "/admin/support/",
        f"/admin/support/lookup?request_id={request_id}",
        f"/admin/support/ticket/{request_id}",
        "/admin/support/ui",
    ]

    for name, (email, password, expected) in identities.items():
        client = app_session.test_client()
        _login(client, email, password=password)
        with client.session_transaction() as session:
            assert session["tenant_id"] == identity_scopes[name][0]
            if name != "superuser":
                assert session["site_id"] == identity_scopes[name][1]
        if name == "unit_portal":
            with app_session.app_context():
                db = get_session()
                try:
                    binding = db.execute(
                        text(
                            "SELECT u.tenant_id, kus.site_id, u.department_id "
                            "FROM users u JOIN kitchen_user_sites kus ON kus.user_id=u.id "
                            "WHERE u.email=:email"
                        ),
                        {"email": email},
                    ).one()
                finally:
                    db.close()
            assert tuple(binding) == (
                data["tenant_a"],
                data["site_a"],
                department_id,
            )
        statuses = [client.get(route).status_code for route in routes]
        expected_statuses = [expected] * len(routes) if isinstance(expected, int) else list(expected)
        assert statuses == expected_statuses
        if expected_statuses[0] != 200:
            assert all(request_id.encode() not in client.get(route).data for route in routes)

    superuser_client = app_session.test_client()
    _login(superuser_client, data["superuser"], password="SuperPassw0rd!2026")
    home = superuser_client.get("/admin/support/").get_json()
    matching = [
        entry for entry in home["recent_warnings"]
        if entry.get("request_id") == request_id
    ]
    assert len(matching) == 1
    assert matching[0]["request_id"] == request_id
    lookup = superuser_client.get(f"/admin/support/lookup?request_id={request_id}")
    assert lookup.status_code == 200
    assert lookup.get_json()["request_id"] == request_id
    assert lookup.get_json()["hits"][0]["request_id"] == request_id
    assert lookup.get_json()["hits"][0]["msg"] == "Mapping 405 to 404"
    ticket = superuser_client.get(f"/admin/support/ticket/{request_id}")
    assert ticket.status_code == 200
    assert ticket.get_json()["request_id"] == request_id
    assert ticket.get_json()["hits"][0]["request_id"] == request_id
    assert ticket.get_json()["hits"][0]["msg"] == "Mapping 405 to 404"


def test_support_deactivated_and_manipulated_context_are_denied(app_session, support_log):
    data = _seed_scope(app_session)
    request_id = support_log
    routes = [
        "/admin/support/",
        f"/admin/support/lookup?request_id={request_id}",
        f"/admin/support/ticket/{request_id}",
        "/admin/support/ui",
    ]
    disabled_clients = []
    disabled_ids = []
    for index, route in enumerate(routes):
        email = f"f12-disabled-{uuid.uuid4().hex}@example.com"
        user_id = _create_user(
            app_session,
            tenant_id=data["tenant_a"],
            email=email,
            role="admin",
            site_id=data["site_a"],
        )
        client = app_session.test_client()
        _login(client, email, password="TargetPassw0rd!2026")
        with client.session_transaction() as session:
            assert session["tenant_id"] == data["tenant_a"]
            assert session["site_id"] == data["site_a"]
        disabled_clients.append((client, route))
        disabled_ids.append(user_id)

    superuser_email = f"f12-disabled-superuser-{uuid.uuid4().hex}@example.com"
    superuser_id = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email=superuser_email,
        role="superuser",
        site_id=data["site_a"],
    )
    superuser_client = app_session.test_client()
    _login(superuser_client, superuser_email, password="TargetPassw0rd!2026")
    disabled_clients.append((superuser_client, routes[0]))
    disabled_ids.append(superuser_id)

    with app_session.app_context():
        db = get_session()
        try:
            for user_id in disabled_ids:
                db.execute(
                    text("UPDATE users SET is_active = 0 WHERE id=:id"),
                    {"id": user_id},
                )
            db.commit()
        finally:
            db.close()
    for client, route in disabled_clients:
        response = client.get(route)
        assert response.status_code == 401
        assert request_id.encode() not in response.data

    for field, value, expected_status in (
        ("role", "superuser", 403),
        ("tenant_id", data["tenant_b"], 401),
        ("site_id", data["site_b"], 401),
    ):
        for route in routes:
            manipulated = app_session.test_client()
            _login(manipulated, data["admin_a"], password="AdminPassw0rd!2026")
            with manipulated.session_transaction() as session:
                assert session["tenant_id"] == data["tenant_a"]
                assert session["site_id"] == data["site_a"]
            with manipulated.session_transaction() as session:
                session[field] = value
            response = manipulated.get(route)
            assert response.status_code == expected_status
            assert request_id.encode() not in response.data


def test_support_auth_version_and_bearer_identity(app_session, support_log):
    data = _seed_scope(app_session)
    request_id = support_log
    routes = [
        "/admin/support/",
        f"/admin/support/lookup?request_id={request_id}",
        f"/admin/support/ticket/{request_id}",
        "/admin/support/ui",
    ]
    session_clients = []
    with app_session.app_context():
        db = get_session()
        try:
            user = db.execute(
                text("SELECT id, auth_version, role, tenant_id FROM users WHERE email=:email"),
                {"email": data["admin_a"]},
            ).one()
            token, _, _ = issue_token_pair(
                user_id=int(user.id),
                role=str(user.role),
                tenant_id=int(user.tenant_id),
                auth_version=int(user.auth_version),
                secret=str(app_session.config["JWT_SECRET"]),
            )
            for route in routes:
                session_client = app_session.test_client()
                _login(session_client, data["admin_a"], password="AdminPassw0rd!2026")
                session_clients.append((session_client, route))
                assert session_client.get(
                    route, headers={"Authorization": f"Bearer {token}"}
                ).status_code == 403
            bearer_token = token
            db.execute(
                text("UPDATE users SET auth_version = auth_version + 1 WHERE id=:id"),
                {"id": int(user.id)},
            )
            db.commit()
        finally:
            db.close()

    for session_client, route in session_clients:
        response = session_client.get(route)
        assert response.status_code == 401
        assert request_id.encode() not in response.data
    for route in routes:
        bearer_client = app_session.test_client()
        response = bearer_client.get(route, headers={"Authorization": f"Bearer {bearer_token}"})
        assert response.status_code == 401
        assert request_id.encode() not in response.data

    superuser_session_clients = []
    with app_session.app_context():
        db = get_session()
        try:
            user = db.execute(
                text("SELECT id, auth_version, role, tenant_id FROM users WHERE email=:email"),
                {"email": data["superuser"]},
            ).one()
            token, _, _ = issue_token_pair(
                user_id=int(user.id),
                role=str(user.role),
                tenant_id=int(user.tenant_id),
                auth_version=int(user.auth_version),
                secret=str(app_session.config["JWT_SECRET"]),
            )
            for route in routes:
                session_client = app_session.test_client()
                _login(session_client, data["superuser"], password="SuperPassw0rd!2026")
                superuser_session_clients.append((session_client, route))
                assert session_client.get(
                    route, headers={"Authorization": f"Bearer {token}"}
                ).status_code == 200
            superuser_token = token
            db.execute(
                text("UPDATE users SET auth_version = auth_version + 1 WHERE id=:id"),
                {"id": int(user.id)},
            )
            db.commit()
        finally:
            db.close()

    for session_client, route in superuser_session_clients:
        response = session_client.get(route)
        assert response.status_code == 401
        assert request_id.encode() not in response.data
    for route in routes:
        bearer_client = app_session.test_client()
        response = bearer_client.get(route, headers={"Authorization": f"Bearer {superuser_token}"})
        assert response.status_code == 401
        assert request_id.encode() not in response.data
