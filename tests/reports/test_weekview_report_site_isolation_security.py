import uuid

from sqlalchemy import text

from core.db import get_session


def _headers(role="admin", tenant_id=1):
    return {"X-User-Role": role, "X-Tenant-Id": str(tenant_id)}


def _seed_report_scope(client):
    site_a1 = str(uuid.uuid4())
    site_a2 = str(uuid.uuid4())
    site_b1 = str(uuid.uuid4())
    dept_a1 = str(uuid.uuid4())
    dept_a2 = str(uuid.uuid4())
    dept_b1 = str(uuid.uuid4())

    with client.application.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO tenants(name, active) VALUES "
                    "(:tenant_a, 1), (:tenant_b, 1)"
                ),
                {
                    "tenant_a": f"Report Tenant A {uuid.uuid4()}",
                    "tenant_b": f"Report Tenant B {uuid.uuid4()}",
                },
            )
            tenant_ids = [
                row[0]
                for row in db.execute(text("SELECT id FROM tenants ORDER BY id")).fetchall()
            ]
            tenant_a, tenant_b = tenant_ids[-2:]
            db.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id, version) VALUES "
                    "(:a1, 'Site A1', :ta, 0), "
                    "(:a2, 'Site A2', :ta, 0), "
                    "(:b1, 'Site B1', :tb, 0)"
                ),
                {"a1": site_a1, "a2": site_a2, "b1": site_b1, "ta": tenant_a, "tb": tenant_b},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES (:d1, :a1, 'Department A1', 'fixed', 0, 0), "
                    "(:d2, :a2, 'Department A2', 'fixed', 0, 0), "
                    "(:d3, :b1, 'Department B1', 'fixed', 0, 0)"
                ),
                {"d1": dept_a1, "d2": dept_a2, "d3": dept_b1, "a1": site_a1, "a2": site_a2, "b1": site_b1},
            )
            db.execute(
                text(
                    "INSERT OR IGNORE INTO users "
                    "(id, tenant_id, username, email, password_hash, role, is_active, auth_version, must_change_password) "
                    "VALUES (1, :tenant_id, 'isolation-admin', 'isolation-admin@example.test', "
                    "'test-hash', 'admin', 1, 1, 0)"
                ),
                {"tenant_id": tenant_a},
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                    "UNIQUE(user_id, tenant_id, site_id))"
                )
            )
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (1, :tenant_id, :site_id)"
                ),
                {"tenant_id": tenant_a, "site_id": site_a1},
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS weekview_residents_count ("
                    "tenant_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, "
                    "week INTEGER NOT NULL, day_of_week INTEGER NOT NULL, meal TEXT NOT NULL, "
                    "count INTEGER NOT NULL DEFAULT 0, "
                    "UNIQUE(tenant_id, department_id, year, week, day_of_week, meal))"
                )
            )
            db.execute(
                text(
                    "INSERT INTO weekview_residents_count "
                    "(tenant_id, department_id, year, week, day_of_week, meal, count) "
                    "VALUES (:tenant_id, :department_id, 2026, 1, 1, 'lunch', :count)"
                ),
                {"tenant_id": str(tenant_a), "department_id": dept_a1, "count": 11},
            )
            db.commit()
        finally:
            db.close()

    with client.session_transaction() as session:
        session.update(
            {
                "user_id": 1,
                "role": "admin",
                "tenant_id": tenant_a,
                "site_id": site_a1,
                "auth_version": 1,
            }
        )

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "site_a1": site_a1,
        "site_a2": site_a2,
        "site_b1": site_b1,
        "dept_a1": dept_a1,
        "dept_a2": dept_a2,
        "dept_b1": dept_b1,
    }


def test_weekview_report_enforces_bound_site_and_tenant(client_admin):
    ids = _seed_report_scope(client_admin)
    base = "/api/reports/weekview?year=2026&week=1"

    own = client_admin.get(
        f"{base}&site_id={ids['site_a1']}&department_id={ids['dept_a1']}",
        headers=_headers(tenant_id=ids["tenant_a"]),
    )
    assert own.status_code == 200
    assert own.get_json()["departments"][0]["department_id"] == ids["dept_a1"]
    assert own.get_json()["departments"][0]["meals"]["lunch"]["residents_total"] == 11

    other_site = client_admin.get(
        f"{base}&site_id={ids['site_a2']}&department_id={ids['dept_a2']}",
        headers=_headers(tenant_id=ids["tenant_a"]),
    )
    assert other_site.status_code == 403
    assert "Site A2" not in other_site.get_data(as_text=True)

    other_tenant = client_admin.get(
        f"{base}&site_id={ids['site_b1']}&department_id={ids['dept_b1']}",
        headers=_headers(tenant_id=ids["tenant_a"]),
    )
    assert other_tenant.status_code == 403
    assert "Site B1" not in other_tenant.get_data(as_text=True)

    wrong_department = client_admin.get(
        f"{base}&site_id={ids['site_a1']}&department_id={ids['dept_a2']}",
        headers=_headers(tenant_id=ids["tenant_a"]),
    )
    assert wrong_department.status_code == 403

    with client_admin.session_transaction() as session:
        session["tenant_id"] = ids["tenant_b"]
        session["site_id"] = ids["site_b1"]
    manipulated_session = client_admin.get(
        f"{base}&site_id={ids['site_b1']}&department_id={ids['dept_b1']}",
        headers=_headers(tenant_id=ids["tenant_b"]),
    )
    assert manipulated_session.status_code == 403


def test_weekview_report_fails_closed_for_missing_binding_and_unauthorized_access(client_admin):
    ids = _seed_report_scope(client_admin)
    with client_admin.application.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "DELETE FROM kitchen_user_sites "
                    "WHERE user_id=1 AND tenant_id=:tenant_id"
                ),
                {"tenant_id": ids["tenant_a"]},
            )
            db.commit()
        finally:
            db.close()

    path = f"/api/reports/weekview?site_id={ids['site_a1']}&year=2026&week=1"
    missing_binding = client_admin.get(path, headers=_headers(tenant_id=ids["tenant_a"]))
    assert missing_binding.status_code == 403
    assert "Site A1" not in missing_binding.get_data(as_text=True)

    anonymous = client_admin.get(path)
    assert anonymous.status_code == 401

    unauthorized_role = client_admin.get(path, headers=_headers("viewer", ids["tenant_a"]))
    assert unauthorized_role.status_code == 403


def test_weekview_report_rejects_historical_extra_binding_for_non_superuser(client_admin):
    ids = _seed_report_scope(client_admin)
    with client_admin.application.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (1, :tenant_id, :site_id)"
                ),
                {"tenant_id": ids["tenant_a"], "site_id": ids["site_a2"]},
            )
            db.commit()
        finally:
            db.close()

    response = client_admin.get(
        f"/api/reports/weekview?site_id={ids['site_a2']}&year=2026&week=1",
        headers=_headers(tenant_id=ids["tenant_a"]),
    )
    assert response.status_code == 403
    assert "Site A2" not in response.get_data(as_text=True)


def test_weekview_report_requires_active_site_and_preserves_superuser_policy(client_admin):
    ids = _seed_report_scope(client_admin)
    with client_admin.session_transaction() as session:
        session.pop("site_id", None)
    missing_active_site = client_admin.get(
        f"/api/reports/weekview?site_id={ids['site_a1']}&year=2026&week=1",
        headers=_headers(tenant_id=ids["tenant_a"]),
    )
    assert missing_active_site.status_code == 403

    with client_admin.application.app_context():
        db = get_session()
        try:
            db.execute(text("UPDATE users SET role='superuser' WHERE id=1"))
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (1, :tenant_id, :site_id)"
                ),
                {"tenant_id": ids["tenant_a"], "site_id": ids["site_a2"]},
            )
            db.commit()
        finally:
            db.close()
    with client_admin.session_transaction() as session:
        session.update({"role": "superuser", "site_id": ids["site_a1"], "tenant_id": ids["tenant_a"]})

    superuser_response = client_admin.get(
        f"/api/reports/weekview?site_id={ids['site_a2']}&year=2026&week=1",
        headers=_headers("superuser", ids["tenant_a"]),
    )
    assert superuser_response.status_code == 200
