import uuid

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.db import get_session
from core.models import Department, Site, Tenant, User


def _seed_report_users(app):
    suffix = uuid.uuid4().hex
    with app.app_context():
        db = get_session()
        try:
            tenant_a = Tenant(name=f"F08 close A {suffix}")
            tenant_b = Tenant(name=f"F08 close B {suffix}")
            db.add_all([tenant_a, tenant_b])
            db.flush()
            site_a1 = Site(id=str(uuid.uuid4()), name="F08 close A1", tenant_id=tenant_a.id)
            site_a2 = Site(id=str(uuid.uuid4()), name="F08 close A2", tenant_id=tenant_a.id)
            site_b1 = Site(id=str(uuid.uuid4()), name="F08 close B1", tenant_id=tenant_b.id)
            db.add_all([site_a1, site_a2, site_b1])
            db.flush()
            department_a1 = Department(
                id=str(uuid.uuid4()),
                site_id=site_a1.id,
                name="F08 close department A1",
            )
            department_b1 = Department(
                id=str(uuid.uuid4()),
                site_id=site_b1.id,
                name="F08 close department B1",
            )
            department_a2 = Department(
                id=str(uuid.uuid4()),
                site_id=site_a2.id,
                name="F08 close department A2",
            )
            db.add_all([department_a1, department_a2, department_b1])
            admin = User(
                tenant_id=tenant_a.id,
                email=f"f08-close-admin-{suffix}@example.test",
                username=f"f08-close-admin-{suffix}",
                password_hash=generate_password_hash("F08ClosePass!2026"),
                role="admin",
                is_active=True,
                auth_version=1,
            )
            superuser = User(
                tenant_id=tenant_a.id,
                email=f"f08-close-superuser-{suffix}@example.test",
                username=f"f08-close-superuser-{suffix}",
                password_hash=generate_password_hash("F08CloseSuper!2026"),
                role="superuser",
                is_active=True,
                auth_version=1,
            )
            db.add_all([admin, superuser])
            db.flush()
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            next_user_id = int(
                db.execute(
                    text(
                        "SELECT MAX(candidate_id) + 1 FROM ("
                        "SELECT COALESCE(MAX(id), 0) AS candidate_id FROM users "
                        "UNION ALL "
                        "SELECT COALESCE(MAX(user_id), 0) AS candidate_id "
                        "FROM kitchen_user_sites"
                        ")"
                    )
                ).scalar_one()
            )
            admin.id = next_user_id
            db.flush()
            superuser.id = next_user_id + 1
            db.flush()
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:user_id, :tenant_id, :site_id)"
                ),
                {"user_id": admin.id, "tenant_id": tenant_a.id, "site_id": site_a1.id},
            )
            db.commit()
            return {
                "tenant_a": tenant_a.id,
                "site_a1": site_a1.id,
                "site_a2": site_a2.id,
                "site_b1": site_b1.id,
                "department_a1": department_a1.id,
                "department_a2": department_a2.id,
                "department_b1": department_b1.id,
                "admin_email": admin.email,
                "superuser_email": superuser.email,
            }
        finally:
            db.close()


def _login(client, email: str, password: str, tenant_id: int) -> None:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Id": str(tenant_id)},
    )
    assert response.status_code == 200, response.get_data(as_text=True)


def _report(client, site_id: str, department_id: str) -> object:
    return client.get(
        "/ui/admin/report/week",
        query_string={
            "site_id": site_id,
            "department_id": department_id,
            "year": 2026,
            "week": 1,
        },
    )


def test_admin_report_week_enforces_real_login_scope(app_session):
    scope = _seed_report_users(app_session)
    client = app_session.test_client()
    _login(client, scope["admin_email"], "F08ClosePass!2026", scope["tenant_a"])

    own = _report(client, scope["site_a1"], "ALL")
    assert own.status_code == 200
    assert b"F08 close A1" in own.data
    assert b"F08 close B1" not in own.data

    with client.session_transaction() as session:
        session["site_id"] = scope["site_a2"]
        session["site_lock"] = False
    cross_site = _report(client, scope["site_a2"], scope["department_a2"])
    assert cross_site.status_code in (401, 403)
    assert b"F08 close A2" not in cross_site.data

    with client.session_transaction() as session:
        session["site_id"] = scope["site_b1"]
        session["site_lock"] = False
    cross_tenant = _report(client, scope["site_b1"], scope["department_b1"])
    assert cross_tenant.status_code in (401, 403)
    assert b"F08 close B1" not in cross_tenant.data
    assert b"F08 close department B1" not in cross_tenant.data

    fresh_client = app_session.test_client()
    _login(fresh_client, scope["admin_email"], "F08ClosePass!2026", scope["tenant_a"])
    with fresh_client.session_transaction() as session:
        session["site_id"] = scope["site_b1"]
        session.pop("site_lock", None)
    missing_lock = _report(fresh_client, scope["site_b1"], scope["department_b1"])
    assert missing_lock.status_code in (401, 403)
    assert b"F08 close B1" not in missing_lock.data


def test_admin_report_week_calls_scope_authorizer(
    app_session,
    monkeypatch,
):
    scope = _seed_report_users(app_session)
    client = app_session.test_client()
    _login(client, scope["admin_email"], "F08ClosePass!2026", scope["tenant_a"])
    calls = []

    def deny_scope(site_id, department_id=None):
        calls.append((site_id, department_id))
        from flask import abort

        abort(403)

    monkeypatch.setattr("core.ui_blueprint._authorize_report_scope", deny_scope)

    response = _report(client, scope["site_a1"], scope["department_a1"])

    assert response.status_code == 403
    assert calls == [(scope["site_a1"], scope["department_a1"])]
    assert b"F08 close A1" not in response.data
    assert b"F08 close department A1" not in response.data


def test_admin_report_week_preserves_superuser_same_tenant_policy(app_session):
    scope = _seed_report_users(app_session)
    client = app_session.test_client()
    _login(client, scope["superuser_email"], "F08CloseSuper!2026", scope["tenant_a"])

    with client.session_transaction() as session:
        session["site_id"] = scope["site_a2"]
    same_tenant = _report(client, scope["site_a2"], "ALL")
    assert same_tenant.status_code == 200

    with client.session_transaction() as session:
        session["site_id"] = scope["site_b1"]
    cross_tenant = _report(client, scope["site_b1"], scope["department_b1"])
    assert cross_tenant.status_code in (302, 401, 403)
    assert b"F08 close B1" not in cross_tenant.data
