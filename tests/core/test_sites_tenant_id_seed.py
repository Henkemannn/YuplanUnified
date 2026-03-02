from sqlalchemy import text

from core.admin_repo import SitesRepo
from core.db import get_session


def test_create_site_sets_tenant_id(app_session):
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS tenants (id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(1, 'TestTenant', 1)"))
            db.commit()
        finally:
            db.close()
        site, _ = SitesRepo().create_site("Tenant-bound site")
        db = get_session()
        try:
            row = db.execute(
                text("SELECT tenant_id FROM sites WHERE id=:id"), {"id": site["id"]}
            ).fetchone()
            assert row is not None
            assert row[0] is not None
        finally:
            db.close()
