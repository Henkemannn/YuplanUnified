from __future__ import annotations

import uuid

from sqlalchemy import text

from core.models import Department, Site, Tenant, User


def _seed_report_scope(app):
    from core.db import get_session

    suffix = uuid.uuid4().hex
    db = get_session()
    try:
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        tenant_a = Tenant(name=f"F08 tenant A {suffix}")
        tenant_b = Tenant(name=f"F08 tenant B {suffix}")
        db.add_all([tenant_a, tenant_b])
        db.flush()

        site_a = Site(id=str(uuid.uuid4()), tenant_id=tenant_a.id, name="F08 Site A")
        site_b = Site(id=str(uuid.uuid4()), tenant_id=tenant_a.id, name="F08 Site B")
        site_c = Site(id=str(uuid.uuid4()), tenant_id=tenant_b.id, name="F08 Site C")
        db.add_all([site_a, site_b, site_c])
        db.flush()

        department_a = Department(id=str(uuid.uuid4()), site_id=site_a.id, name="F08 Department A")
        department_b = Department(id=str(uuid.uuid4()), site_id=site_b.id, name="F08 Department B")
        db.add_all([department_a, department_b])
        user = User(
            tenant_id=tenant_a.id,
            email=f"f08-{suffix}@example.test",
            password_hash="fixture-only",
            role="admin",
            auth_version=1,
        )
        db.add(user)
        db.flush()
        db.execute(text("DELETE FROM kitchen_user_sites WHERE user_id=:user_id"), {"user_id": user.id})
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
            "tenant_id": tenant_a.id,
            "site_a": site_a.id,
            "site_b": site_b.id,
            "site_c": site_c.id,
            "department_a": department_a.id,
            "department_b": department_b.id,
        }
    finally:
        db.close()


def _authenticate_bound_admin(client, scope):
    with client.session_transaction() as session:
        session.update(
            {
                "user_id": scope["user_id"],
                "role": "admin",
                "tenant_id": scope["tenant_id"],
                "site_id": scope["site_a"],
                "auth_version": 1,
            }
        )


def test_report_ui_and_exports_enforce_bound_site(app_session):
    scope = _seed_report_scope(app_session)
    client = app_session.test_client()
    _authenticate_bound_admin(client, scope)

    routes = (
        "/ui/reports/weekview",
        "/ui/reports/weekly",
        "/ui/reports/weekly.csv",
        "/ui/reports/weekly.xlsx",
        "/ui/reports/weekly.pdf",
    )
    own_query = {"site_id": scope["site_a"], "year": 2026, "week": 1}
    for route in routes:
        response = client.get(route, query_string=own_query)
        assert response.status_code == 200

    for route in routes:
        response = client.get(
            route,
            query_string={"site_id": scope["site_b"], "year": 2026, "week": 1},
        )
        assert response.status_code == 403
        assert b"F08 Site B" not in response.data

        response = client.get(
            route,
            query_string={"site_id": scope["site_c"], "year": 2026, "week": 1},
        )
        assert response.status_code == 403
        assert b"F08 Site C" not in response.data


def test_report_department_and_missing_binding_fail_closed(app_session):
    scope = _seed_report_scope(app_session)
    client = app_session.test_client()
    _authenticate_bound_admin(client, scope)

    response = client.get(
        "/ui/reports/weekview",
        query_string={
            "site_id": scope["site_a"],
            "department_id": scope["department_b"],
            "year": 2026,
            "week": 1,
        },
    )
    assert response.status_code == 403
    assert b"F08 Department B" not in response.data

    with client.session_transaction() as session:
        session.pop("site_id", None)
    response = client.get(
        "/ui/reports/weekly.csv",
        query_string={"site_id": scope["site_a"], "year": 2026, "week": 1},
    )
    assert response.status_code in (401, 403)


def test_superuser_keeps_explicit_same_tenant_scope(app_session):
    scope = _seed_report_scope(app_session)
    from core.db import get_session

    db = get_session()
    try:
        user = User(
            tenant_id=scope["tenant_id"],
            email=f"f08-superuser-{uuid.uuid4().hex}@example.test",
            password_hash="fixture-only",
            role="superuser",
            auth_version=1,
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
                "tenant_id": scope["tenant_id"],
                "site_id": scope["site_a"],
                "auth_version": 1,
            }
        )

    response = client.get(
        "/ui/reports/weekly.csv",
        query_string={"site_id": scope["site_b"], "year": 2026, "week": 1},
        headers={"If-None-Match": 'W/"report:old"'},
    )
    assert response.status_code == 200

    response = client.get(
        "/ui/reports/weekly.csv",
        query_string={"site_id": scope["site_c"], "year": 2026, "week": 1},
    )
    assert response.status_code == 403
