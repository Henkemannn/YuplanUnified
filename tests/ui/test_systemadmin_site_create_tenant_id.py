from flask.testing import FlaskClient
from sqlalchemy import text


def test_systemadmin_site_create_sets_tenant_id(app_session, client: FlaskClient):
    # Create a tenant
    with app_session.app_context():
        db = app_session.extensions["sqlalchemy"].db.session.bind.connect() if False else None  # unused, using get_session directly
    from core.db import get_session
    from core.models import Tenant, User
    from werkzeug.security import generate_password_hash

    # Seed superuser and tenant in DB
    with app_session.app_context():
        db = get_session()
        try:
            # Superuser
            u = db.query(User).filter(User.email == "sysadmin-create@example.com").first()
            if not u:
                u = User(
                    tenant_id=1,
                    email="sysadmin-create@example.com",
                    username="sysadmin-create@example.com",
                    password_hash=generate_password_hash("superpass"),
                    role="superuser",
                    is_active=True,
                    unit_id=None,
                )
                db.add(u)
                db.commit()
            # Tenant
            t = Tenant(name="Test Kund A")
            db.add(t)
            db.commit()
            tenant_id = t.id
        finally:
            db.close()

    # Login as superuser
    client.post(
        "/ui/login",
        data={"email": "sysadmin-create@example.com", "password": "superpass"},
        follow_redirects=True,
    )

    # Create a site for the tenant
    resp = client.post(
        f"/ui/systemadmin/customers/{tenant_id}/sites/create",
        data={
            "site_name": "Östergården",
            "admin_email": "admin.ost@example.com",
            "admin_password": "Passw0rd!",
            "sf_weekview": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Verify site exists and has tenant_id set (when column exists)
    db2 = get_session()
    try:
        # Ensure table exists
        db2.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT, version INTEGER, tenant_id INTEGER)"))
        rows = db2.execute(text("PRAGMA table_info('sites')")).fetchall()
        has_tenant = any(str(c[1]) == "tenant_id" for c in rows)
        row = db2.execute(text("SELECT id, name, tenant_id FROM sites WHERE name=:n ORDER BY ROWID DESC LIMIT 1"), {"n": "Östergården"}).fetchone()
        assert row is not None
        site_id = str(row[0])
        if has_tenant:
            assert row[2] == tenant_id

        admin_row = db2.execute(
            text("SELECT id FROM users WHERE email=:e LIMIT 1"),
            {"e": "admin.ost@example.com"},
        ).fetchone()
        assert admin_row is not None
        admin_user_id = int(admin_row[0])

        ucols = db2.execute(text("PRAGMA table_info('users')")).fetchall()
        has_user_site_id = any(str(c[1]) == "site_id" for c in ucols)
        if has_user_site_id:
            bound = db2.execute(
                text("SELECT site_id FROM users WHERE id=:uid"),
                {"uid": admin_user_id},
            ).fetchone()
            assert bound is not None and str(bound[0] or "") == site_id
        else:
            db2.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            bound = db2.execute(
                text("SELECT site_id FROM kitchen_user_sites WHERE user_id=:uid LIMIT 1"),
                {"uid": admin_user_id},
            ).fetchone()
            assert bound is not None and str(bound[0] or "") == site_id
    finally:
        db2.close()


def test_systemadmin_can_add_additional_admin_for_site(app_session, client: FlaskClient):
    from core.db import get_session
    from core.models import Tenant, User
    from werkzeug.security import generate_password_hash

    with app_session.app_context():
        db = get_session()
        try:
            su = db.query(User).filter(User.email == "sysadmin-add-admin@example.com").first()
            if not su:
                su = User(
                    tenant_id=1,
                    email="sysadmin-add-admin@example.com",
                    username="sysadmin-add-admin@example.com",
                    password_hash=generate_password_hash("superpass"),
                    role="superuser",
                    is_active=True,
                    unit_id=None,
                )
                db.add(su)
                db.commit()
            t = Tenant(name="Test Kund B")
            db.add(t)
            db.commit()
            tenant_id = int(t.id)
            db.execute(
                text("INSERT INTO sites(id,name,version,tenant_id) VALUES(:id,:name,0,:tid)"),
                {"id": "site-admin-test", "name": "Site Admin Test", "tid": tenant_id},
            )
            db.commit()
        finally:
            db.close()

    client.post(
        "/ui/login",
        data={"email": "sysadmin-add-admin@example.com", "password": "superpass"},
        follow_redirects=True,
    )

    resp = client.post(
        f"/ui/systemadmin/customers/{tenant_id}/sites/site-admin-test/admins/create",
        data={
            "admin_full_name": "Admin Two",
            "admin_email": "admin.two@example.com",
            "admin_password": "Passw0rd!",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db2 = get_session()
    try:
        u = db2.execute(
            text("SELECT id FROM users WHERE email=:e LIMIT 1"),
            {"e": "admin.two@example.com"},
        ).fetchone()
        assert u is not None
        uid = int(u[0])

        ucols = db2.execute(text("PRAGMA table_info('users')")).fetchall()
        has_user_site_id = any(str(c[1]) == "site_id" for c in ucols)
        if has_user_site_id:
            row = db2.execute(text("SELECT site_id FROM users WHERE id=:uid"), {"uid": uid}).fetchone()
            assert row is not None and str(row[0] or "") == "site-admin-test"
        else:
            row = db2.execute(
                text("SELECT site_id FROM kitchen_user_sites WHERE user_id=:uid LIMIT 1"),
                {"uid": uid},
            ).fetchone()
            assert row is not None and str(row[0] or "") == "site-admin-test"
    finally:
        db2.close()
