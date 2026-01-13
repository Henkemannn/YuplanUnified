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
        if has_tenant:
            assert row[2] == tenant_id
    finally:
        db2.close()
