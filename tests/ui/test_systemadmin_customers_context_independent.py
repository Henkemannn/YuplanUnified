from __future__ import annotations

from flask.testing import FlaskClient
from sqlalchemy import text


def test_systemadmin_customers_not_filtered_by_context(app_session, client: FlaskClient):
    from core.db import get_session
    from core.models import Tenant

    site_a = "ctx-site-a"
    site_b = "ctx-site-b"

    tenant2_id = None
    with app_session.app_context():
        db = get_session()
        try:
            tenant2 = Tenant(name="Tenant Two Context")
            db.add(tenant2)
            db.commit()
            db.refresh(tenant2)
            tenant2_id = int(tenant2.id)

            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :n, :t, 0)"
                ),
                {"id": site_a, "n": "Context Site A", "t": 1},
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:id, :n, :t, 0)"
                ),
                {"id": site_b, "n": "Context Site B", "t": tenant2_id},
            )
            db.commit()
        finally:
            db.close()
    assert tenant2_id is not None

    with client.session_transaction() as sess:
        sess["role"] = "superuser"
        sess["user_id"] = "ctx-superuser"
        sess["tenant_id"] = 1
        sess["site_id"] = site_a

    headers = {"X-User-Role": "superuser", "X-Tenant-Id": "1"}

    resp = client.get("/ui/systemadmin/customers", headers=headers)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Tenant Two Context" in html

    sites_resp = client.get(
        f"/ui/systemadmin/customers/{tenant2_id}/sites",
        headers=headers,
    )
    assert sites_resp.status_code == 200
    sites_html = sites_resp.data.decode("utf-8")
    assert "Context Site B" in sites_html
