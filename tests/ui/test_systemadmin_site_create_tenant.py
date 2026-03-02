import uuid

from sqlalchemy import text


def test_systemadmin_site_create_sets_tenant_id(app_session):
    client = app_session.test_client()
    site_name = f"Tenant Guard {uuid.uuid4().hex[:6]}"

    resp = client.post(
        "/ui/systemadmin/customers/1/sites/create",
        data={
            "site_name": site_name,
            "admin_email": "site-admin@example.com",
            "admin_password": "Passw0rd!",
        },
        headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app_session.app_context():
        from core.db import get_session

        db = get_session()
        try:
            row = db.execute(
                text("SELECT tenant_id FROM sites WHERE name=:n"), {"n": site_name}
            ).fetchone()
            assert row is not None
            assert int(row[0]) == 1
        finally:
            db.close()
