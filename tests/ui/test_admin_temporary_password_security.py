from __future__ import annotations

import re
import os
import tempfile
import uuid

import pytest
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Site, Tenant, User


@pytest.fixture
def f14_client():
    import core.db as db_module

    previous_engine = db_module._engine
    previous_url = str(previous_engine.url) if previous_engine is not None else None
    previous_builder = os.environ.get("BUILDER_DB_PATH")
    temp_root = tempfile.TemporaryDirectory(prefix="yuplan-f14-")
    with temp_root as temp_dir:
        main_db = os.path.join(temp_dir, "main.db")
        builder_db = os.path.join(temp_dir, "builder.db")
        os.environ["BUILDER_DB_PATH"] = builder_db
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "f14-test-secret",
                "database_url": f"sqlite:///{main_db}",
                "BUILDER_DB_PATH": builder_db,
                "FORCE_DB_REINIT": True,
            }
        )
        app.config.update(
            {"YUPLAN_STRICT_CSRF": True, "STRICT_CSRF_IN_TESTS": True}
        )
        with app.app_context():
            create_all()
            db = get_session()
            try:
                tenant = Tenant(name=f"F14 tenant {uuid.uuid4().hex}")
                db.add(tenant)
                db.flush()
                site = Site(
                    id=f"f14-site-{uuid.uuid4().hex}",
                    name="F14 primary site",
                    tenant_id=tenant.id,
                )
                db.add(site)
                db.flush()
                email = f"f14-admin-{uuid.uuid4().hex}@example.test"
                admin = User(
                    tenant_id=tenant.id,
                    email=email,
                    username=email,
                    password_hash=generate_password_hash("F14-admin-password!"),
                    role="admin",
                )
                db.add(admin)
                db.flush()
                db.execute(
                    text(
                        "CREATE TABLE kitchen_user_sites ("
                        "user_id INTEGER PRIMARY KEY, "
                        "tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                    )
                )
                db.execute(
                    text(
                        "INSERT INTO kitchen_user_sites "
                        "(user_id, tenant_id, site_id) "
                        "VALUES (:user_id, :tenant_id, :site_id)"
                    ),
                    {
                        "user_id": admin.id,
                        "tenant_id": tenant.id,
                        "site_id": site.id,
                    },
                )
                db.commit()
                tenant_id = int(tenant.id)
                site_id = str(site.id)
            finally:
                db.close()
        client = app.test_client()
        login = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "F14-admin-password!",
            },
        )
        assert login.status_code == 200
        with client.session_transaction() as session:
            assert session["tenant_id"] == tenant_id
            assert session["site_id"] == site_id
        yield client
        temp_root._ignore_cleanup_errors = True
        if db_module._SessionFactory is not None:
            db_module._SessionFactory.remove()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._SessionFactory = None
        db_module._engine = None
        if previous_url is not None:
            from core.db import init_engine

            init_engine(previous_url, force=True)
        if previous_builder is None:
            os.environ.pop("BUILDER_DB_PATH", None)
        else:
            os.environ["BUILDER_DB_PATH"] = previous_builder


@pytest.fixture(autouse=True)
def strict_csrf_config():
    yield


def _scope(client) -> tuple[int, str]:
    with client.session_transaction() as session:
        return int(session["tenant_id"]), str(session["site_id"])


def _seed_target(
    client,
    *,
    tenant_id: int | None = None,
    site_id: str | None = None,
    role: str = "staff",
    refresh_token_jti: str | None = "old-refresh",
) -> int:
    current_tenant, current_site = _scope(client)
    tenant_id = current_tenant if tenant_id is None else tenant_id
    site_id = current_site if site_id is None else site_id
    suffix = uuid.uuid4().hex
    email = f"f14-target-{suffix}@example.test"
    username = f"f14-target-{suffix}"
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO users "
                "(tenant_id, email, password_hash, role, username, full_name, is_active, "
                "auth_version, refresh_token_jti, must_change_password) "
                "VALUES (:tenant_id, :email, :password_hash, :role, :username, "
                "'F14 Target', 1, 1, :refresh_token_jti, 0)"
            ),
            {
                "tenant_id": tenant_id,
                "email": email,
                "password_hash": generate_password_hash("Old-password-123!"),
                "role": role,
                "username": username,
                "refresh_token_jti": refresh_token_jti,
            },
        )
        db.commit()
        user_id = int(
            db.execute(
                text("SELECT id FROM users WHERE email=:email"),
                {"email": email},
            ).scalar_one()
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {"user_id": user_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        db.commit()
        return user_id
    finally:
        db.close()


def _form_data(client, user_id: int) -> dict[str, str]:
    response = client.get("/ui/admin/users")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    form_match = re.search(
        rf'<form[^>]+action="/ui/admin/users/{user_id}/reset-password".*?</form>',
        html,
        flags=re.DOTALL,
    )
    assert form_match is not None
    form = form_match.group(0)
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', form)
    version_match = re.search(r'name="auth_version" value="([^"]+)"', form)
    assert csrf_match is not None
    assert version_match is not None
    return {
        "csrf_token": csrf_match.group(1),
        "auth_version": version_match.group(1),
    }


def _user_state(user_id: int) -> tuple[str, int, str | None]:
    db = get_session()
    try:
        return tuple(
            db.execute(
                text(
                    "SELECT password_hash, auth_version, refresh_token_jti "
                    "FROM users WHERE id=:user_id"
                ),
                {"user_id": user_id},
            ).one()
        )
    finally:
        db.close()


def _user_email(user_id: int) -> str:
    db = get_session()
    try:
        return str(
            db.execute(
                text("SELECT email FROM users WHERE id=:user_id"),
                {"user_id": user_id},
            ).scalar_one()
        )
    finally:
        db.close()


def test_real_admin_reset_has_no_session_cookie_or_log_secret(f14_client, caplog):
    client = f14_client
    user_id = _seed_target(client)
    form = _form_data(client, user_id)

    response = client.post(
        f"/ui/admin/users/{user_id}/reset-password",
        data=form,
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, private, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    body = response.get_data(as_text=True)
    match = re.search(r"<code>([^<]+)</code>", body)
    assert match is not None
    temporary_password = match.group(1)
    assert "F14 Target" in body
    assert "kan inte" in body and "hämtas igen" in body
    assert response.headers.get("Location") is None
    assert all(
        temporary_password not in header
        for header in response.headers.getlist("Set-Cookie")
    )
    with client.session_transaction() as session:
        assert temporary_password not in repr(dict(session))
    assert temporary_password not in caplog.text

    password_hash, auth_version, refresh_token_jti = _user_state(user_id)
    assert check_password_hash(password_hash, temporary_password)
    assert auth_version == 2
    assert refresh_token_jti is None
    db = get_session()
    try:
        audit_rows = db.execute(
            text(
                "SELECT event, payload FROM audit_events "
                "WHERE tenant_id=(SELECT tenant_id FROM users WHERE id=:user_id)"
            ),
            {"user_id": user_id},
        ).all()
    finally:
        db.close()
    assert temporary_password not in repr(audit_rows)
    assert temporary_password not in repr(client.application.extensions)

    listed = client.get("/ui/admin/users")
    assert listed.status_code == 200
    assert temporary_password not in listed.get_data(as_text=True)


def test_replay_does_not_mutate_and_current_form_allows_new_reset(f14_client):
    client = f14_client
    user_id = _seed_target(client)
    form = _form_data(client, user_id)
    first = client.post(f"/ui/admin/users/{user_id}/reset-password", data=form)
    assert first.status_code == 200
    first_password = re.search(r"<code>([^<]+)</code>", first.get_data(as_text=True))
    assert first_password is not None
    first_state = _user_state(user_id)

    replay = client.post(
        f"/ui/admin/users/{user_id}/reset-password",
        data=form,
        follow_redirects=False,
    )
    assert replay.status_code == 302
    assert _user_state(user_id) == first_state

    current_form = _form_data(client, user_id)
    second = client.post(
        f"/ui/admin/users/{user_id}/reset-password", data=current_form
    )
    assert second.status_code == 200
    second_password = re.search(
        r"<code>([^<]+)</code>", second.get_data(as_text=True)
    )
    assert second_password is not None
    assert second_password.group(1) != first_password.group(1)
    assert _user_state(user_id)[1] == 3


@pytest.mark.parametrize("version", [None, "not-a-version", "0"])
def test_invalid_or_missing_version_does_not_mutate(f14_client, version):
    client = f14_client
    user_id = _seed_target(client)
    form = _form_data(client, user_id)
    form.pop("auth_version")
    if version is not None:
        form["auth_version"] = version
    response = client.post(
        f"/ui/admin/users/{user_id}/reset-password",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert _user_state(user_id)[1] == 1


def test_invalid_csrf_does_not_mutate(f14_client):
    client = f14_client
    user_id = _seed_target(client)
    form = _form_data(client, user_id)
    form["csrf_token"] = "invalid-csrf-token"
    response = client.post(
        f"/ui/admin/users/{user_id}/reset-password",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code in (400, 403)
    assert _user_state(user_id)[1] == 1


def test_target_scope_and_role_authorization_hold_with_current_versions(
    f14_client,
):
    client = f14_client
    tenant_id, site_id = _scope(client)
    visible_target = _seed_target(client)
    csrf_token = _form_data(client, visible_target)["csrf_token"]
    same_tenant_other_site = str(uuid.uuid4())
    cross_tenant = tenant_id + 1000
    cross_tenant_site = str(uuid.uuid4())
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR IGNORE INTO sites (id, tenant_id, name) "
                "VALUES (:site_id, :tenant_id, 'Other F14 site')"
            ),
            {"site_id": same_tenant_other_site, "tenant_id": tenant_id},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO tenants (id, name) "
                "VALUES (:tenant_id, 'Other F14 tenant')"
            ),
            {"tenant_id": cross_tenant},
        )
        db.execute(
            text(
                "INSERT OR IGNORE INTO sites (id, tenant_id, name) "
                "VALUES (:site_id, :tenant_id, 'Other F14 tenant site')"
            ),
            {"site_id": cross_tenant_site, "tenant_id": cross_tenant},
        )
        db.commit()
    finally:
        db.close()

    for target_tenant, target_site, role in (
        (tenant_id, same_tenant_other_site, "staff"),
        (cross_tenant, cross_tenant_site, "staff"),
        (tenant_id, site_id, "superuser"),
    ):
        user_id = _seed_target(
            client,
            tenant_id=target_tenant,
            site_id=target_site,
            role=role,
            refresh_token_jti="protected-refresh",
        )
        before = _user_state(user_id)
        current_version = str(_user_state(user_id)[1])
        response = client.post(
            f"/ui/admin/users/{user_id}/reset-password",
            data={"csrf_token": csrf_token, "auth_version": current_version},
            follow_redirects=False,
        )
        assert response.status_code in (302, 404)
        password_hash, auth_version, refresh_token_jti = _user_state(user_id)
        assert (password_hash, auth_version, refresh_token_jti) == before
        assert auth_version == 1
        assert refresh_token_jti == "protected-refresh"
        assert check_password_hash(password_hash, "Old-password-123!")


def test_unauthorized_real_actor_with_valid_csrf_cannot_reset(f14_client):
    admin_client = f14_client
    target_id = _seed_target(admin_client)
    actor_id = _seed_target(admin_client, role="staff")
    actor_client = admin_client.application.test_client()
    actor_login = actor_client.post(
        "/auth/login",
        json={
            "email": _user_email(actor_id),
            "password": "Old-password-123!",
        },
    )
    assert actor_login.status_code == 200
    csrf_token = (actor_login.get_json() or {}).get("csrf_token")
    assert csrf_token
    before = _user_state(target_id)
    response = actor_client.post(
        f"/ui/admin/users/{target_id}/reset-password",
        data={
            "csrf_token": csrf_token,
            "auth_version": str(before[1]),
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 403, 404)
    assert _user_state(target_id) == before


def test_reset_failure_uses_safe_error_without_exception_text(
    f14_client, monkeypatch
):
    from core.admin_user_repo import AdminUserRepo

    client = f14_client
    user_id = _seed_target(client)
    form = _form_data(client, user_id)

    def fail_reset(*args, **kwargs):
        raise RuntimeError("synthetic-secret-error")

    monkeypatch.setattr(AdminUserRepo, "reset_password", fail_reset)
    response = client.post(
        f"/ui/admin/users/{user_id}/reset-password",
        data=form,
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "synthetic-secret-error" not in body
    assert "Kunde inte återställa lösenordet" in body
    assert _user_state(user_id)[1] == 1
