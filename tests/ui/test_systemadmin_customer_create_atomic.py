import uuid

from sqlalchemy import text

from core.app_factory import create_app
from core.db import create_all


def test_systemadmin_customer_create_atomic():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
    client = app.test_client()
    suffix = uuid.uuid4().hex[:8]
    tenant_name = f"Atomic Tenant {suffix}"
    site_name = f"Atomic Site {suffix}"
    admin_email = f"atomic-admin-{suffix}@example.com"
    with client.session_transaction() as sess:
        sess["wizard_new_customer"] = {
            "tenant_name": tenant_name,
            "customer_type": "kommun",
        }

    resp = client.post(
        "/ui/systemadmin/customers/new/admin",
        data={
            "site_name": site_name,
            "admin_email": admin_email,
            "admin_password": "Passw0rd!",
        },
        headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        from core.db import get_session

        db = get_session()
        try:
            trow = db.execute(
                text("SELECT id FROM tenants WHERE name=:n"), {"n": tenant_name}
            ).fetchone()
            assert trow is not None
            tid = int(trow[0])
            srow = db.execute(
                text("SELECT tenant_id FROM sites WHERE name=:n"), {"n": site_name}
            ).fetchone()
            assert srow is not None
            assert int(srow[0]) == tid
        finally:
            db.close()
