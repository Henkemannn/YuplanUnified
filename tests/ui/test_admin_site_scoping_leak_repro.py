from flask.testing import FlaskClient
from sqlalchemy import text


def _create_superuser_and_tenants(app_session):
    from core.db import get_session
    from core.models import Tenant, User
    from werkzeug.security import generate_password_hash

    with app_session.app_context():
        db = get_session()
        try:
            # Superuser
            u = db.query(User).filter(User.email == "sa-leak-repro@example.com").first()
            if not u:
                u = User(
                    tenant_id=1,
                    email="sa-leak-repro@example.com",
                    username="sa-leak-repro@example.com",
                    password_hash=generate_password_hash("superpass"),
                    role="superuser",
                    is_active=True,
                    unit_id=None,
                )
                db.add(u)
            # Tenants
            ta = Tenant(name="Tenant A")
            tb = Tenant(name="Tenant B")
            db.add(ta)
            db.add(tb)
            db.commit()
            return ta.id, tb.id
        finally:
            db.close()


def _create_site(client: FlaskClient, tenant_id: int, name: str, admin_email: str):
    # Use canonical admin UI route to create a site under a tenant
    resp = client.post(
        f"/ui/systemadmin/customers/{tenant_id}/sites/create",
        data={
            "site_name": name,
            "admin_email": admin_email,
            "admin_password": "Passw0rd!",
            "sf_weekview": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


def _get_site_id_by_name(app_session, name: str) -> str:
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM sites WHERE name=:n"), {"n": name}).fetchone()
            assert row is not None
            return str(row[0])
        finally:
            db.close()


def _create_department(client: FlaskClient, name: str):
    # Create via site-admin route (requires active site)
    resp = client.post(
        "/ui/admin/departments/new",
        data={
            "name": name,
            "resident_count": "12",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


def _get_department_id(app_session, site_id: str, name: str) -> str:
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM departments WHERE site_id=:sid AND name=:n"), {"sid": site_id, "n": name}).fetchone()
            assert row is not None
            return str(row[0])
        finally:
            db.close()


def _get_diet_type_id(app_session, site_id: str, name: str) -> str:
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM dietary_types WHERE site_id=:sid AND name=:n"), {"sid": site_id, "n": name}).fetchone()
            assert row is not None
            return str(row[0])
        finally:
            db.close()


def test_admin_isolation_leak_repro(app_session, client: FlaskClient):
    # Seed superuser + two tenants
    tid_a, tid_b = _create_superuser_and_tenants(app_session)

    # Login as superuser
    client.post(
        "/ui/login",
        data={"email": "sa-leak-repro@example.com", "password": "superpass"},
        follow_redirects=True,
    )

    # Create two sites with names forcing LIMIT 1 fallback to pick Site B
    _create_site(client, tid_a, name="zzz Site A", admin_email="admin.a@example.com")
    _create_site(client, tid_b, name="aaa Site B", admin_email="admin.b@example.com")

    site_a = _get_site_id_by_name(app_session, "zzz Site A")
    site_b = _get_site_id_by_name(app_session, "aaa Site B")

    # Switch to Site A admin
    resp = client.get(f"/ui/systemadmin/switch-site/{site_a}", follow_redirects=True)
    assert resp.status_code == 200

    # Create Department A under Site A
    _create_department(client, "Avd A")
    dept_a = _get_department_id(app_session, site_a, "Avd A")

    # Create Diet A via site-admin route (strictly uses active site)
    resp = client.post(
        "/ui/admin/specialkost/new",
        data={"name": "Diet A"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    dt_a_id = _get_diet_type_id(app_session, site_a, "Diet A")

    # Link Diet A default to Department A
    resp = client.post(
        f"/ui/admin/departments/{dept_a}/edit",
        data={
            "name": "Avd A",
            "resident_count": "12",
            f"diet_default_{dt_a_id}": "3",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Switch to Site B admin
    resp = client.get(f"/ui/systemadmin/switch-site/{site_b}", follow_redirects=True)
    assert resp.status_code == 200

    # Create Department B and Diet B
    _create_department(client, "Avd B")
    dept_b = _get_department_id(app_session, site_b, "Avd B")
    resp = client.post(
        "/ui/admin/specialkost/new",
        data={"name": "Diet B"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    dt_b_id = _get_diet_type_id(app_session, site_b, "Diet B")

    # Link Diet B default to Department B
    resp = client.post(
        f"/ui/admin/departments/{dept_b}/edit",
        data={
            "name": "Avd B",
            "resident_count": "10",
            f"diet_default_{dt_b_id}": "2",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Assert isolation via UI: on Site B, list shows only Avd B and Diet B
    page = client.get("/ui/admin/departments", follow_redirects=True)
    assert b"Avd B" in page.data and b"Avd A" not in page.data
    # Repro leakage: request args should NOT override active site; current bug uses request args fallback
    page = client.get(f"/ui/admin/specialkost?site_id={site_a}", follow_redirects=True)
    # Expectation: still see Diet B (active site), NOT Diet A
    assert b"Diet B" in page.data and b"Diet A" not in page.data

    # Assert topbar context shows Site B name
    page = client.get("/ui/admin", follow_redirects=True)
    assert b"aaa Site B" in page.data

    # DB assertions: departments site_id differ and diets are site-scoped
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            ra = db.execute(text("SELECT site_id FROM departments WHERE id=:i"), {"i": dept_a}).fetchone()
            rb = db.execute(text("SELECT site_id FROM departments WHERE id=:i"), {"i": dept_b}).fetchone()
            assert ra and rb and str(ra[0]) != str(rb[0])
            da = db.execute(text("SELECT site_id FROM dietary_types WHERE name='Diet A'"), {}).fetchone()
            db_row_b = db.execute(text("SELECT site_id FROM dietary_types WHERE name='Diet B'"), {}).fetchone()
            assert da and db_row_b and str(da[0]) != str(db_row_b[0])
        finally:
            db.close()
