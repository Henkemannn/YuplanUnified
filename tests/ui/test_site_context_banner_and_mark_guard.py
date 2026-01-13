from flask.testing import FlaskClient
from sqlalchemy import text


def _seed_superuser_and_tenants(app_session):
    from core.db import get_session
    from core.models import Tenant, User
    from werkzeug.security import generate_password_hash

    with app_session.app_context():
        db = get_session()
        try:
            # Superuser
            u = db.query(User).filter(User.email == "sa-banner@example.com").first()
            if not u:
                u = User(
                    tenant_id=1,
                    email="sa-banner@example.com",
                    username="sa-banner@example.com",
                    password_hash=generate_password_hash("superpass"),
                    role="superuser",
                    is_active=True,
                    unit_id=None,
                )
                db.add(u)
            # Tenants: query-or-create by name to avoid UNIQUE violations
            ta = db.query(Tenant).filter(Tenant.name == "Tenant BA").first()
            if not ta:
                ta = Tenant(name="Tenant BA")
                db.add(ta)
                db.flush()
            tb = db.query(Tenant).filter(Tenant.name == "Tenant BB").first()
            if not tb:
                tb = Tenant(name="Tenant BB")
                db.add(tb)
                db.flush()
            db.commit()
            return ta.id, tb.id
        finally:
            db.close()


def _create_site(client: FlaskClient, tenant_id: int, name: str, admin_email: str):
    resp = client.post(
        f"/ui/systemadmin/customers/{tenant_id}/sites/create",
        data={
            "site_name": name,
            "admin_email": admin_email,
            "admin_password": "Passw0rd!",
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
    resp = client.post(
        "/ui/admin/departments/new",
        data={
            "name": name,
            "resident_count": "7",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_A_query_param_site_id_does_not_switch_site_and_shows_banner(app_session, client: FlaskClient):
    ta, tb = _seed_superuser_and_tenants(app_session)
    client.post("/ui/login", data={"email": "sa-banner@example.com", "password": "superpass"}, follow_redirects=True)
    _create_site(client, ta, name="Site A-CTX", admin_email="adm.a@x")
    _create_site(client, tb, name="Site B-CTX", admin_email="adm.b@x")
    site_a = _get_site_id_by_name(app_session, "Site A-CTX")
    site_b = _get_site_id_by_name(app_session, "Site B-CTX")

    # Switch to Site A and open admin; ensure topbar contains Site A
    client.get(f"/ui/systemadmin/switch-site/{site_a}", follow_redirects=True)
    page = client.get(f"/ui/admin?site_id={site_b}", follow_redirects=True)
    assert page.status_code == 200
    body = page.data
    # Topbar/badge must still reflect Site A, not Site B
    assert b"Site A-CTX" in body and b"Site B-CTX" not in body
    # SSR banner should render due to mismatch
    assert b"Du har bytt arbetsplats i en annan flik" in body


def test_B_mark_done_wrong_site_returns_403_and_no_write(app_session, client: FlaskClient):
    from datetime import date
    ta, tb = _seed_superuser_and_tenants(app_session)
    client.post("/ui/login", data={"email": "sa-banner@example.com", "password": "superpass"}, follow_redirects=True)
    _create_site(client, ta, name="Site A-MARK", admin_email="adm.a2@x")
    _create_site(client, tb, name="Site B-MARK", admin_email="adm.b2@x")
    site_a = _get_site_id_by_name(app_session, "Site A-MARK")
    site_b = _get_site_id_by_name(app_session, "Site B-MARK")

    # Switch to Site A and create a department
    client.get(f"/ui/systemadmin/switch-site/{site_a}", follow_redirects=True)
    _create_department(client, "Avd Mark A")

    # Lookup department id
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            dep_row = db.execute(text("SELECT id FROM departments WHERE site_id=:s AND name='Avd Mark A'"), {"s": site_a}).fetchone()
            assert dep_row is not None
            dep_id = str(dep_row[0])
        finally:
            db.close()

    # Try to mark done for Site B (wrong site) -> 403
    today = date.today().isoformat()
    resp = client.post(
        "/ui/planera/day/mark_done",
        data={
            "site_id": site_b,
            "date": today,
            "meal": "lunch",
            "department_ids": [dep_id],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 403

    # Verify no DB write for Site B
    with app_session.app_context():
        db = get_session()
        try:
            rows = db.execute(text("SELECT COUNT(*) FROM meal_registrations WHERE site_id=:s"), {"s": site_b}).fetchone()
            count_b = int(rows[0]) if rows else 0
            assert count_b == 0
        finally:
            db.close()
