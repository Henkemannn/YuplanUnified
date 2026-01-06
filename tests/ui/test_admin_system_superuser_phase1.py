from flask.testing import FlaskClient
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session


def _seed_initial(db):
    if not db.execute(text("SELECT 1 FROM sites WHERE id='s1'")):  # pragma: no cover - best effort
        db.execute(text("INSERT OR REPLACE INTO sites(id,name) VALUES('s1','Site 1')"))
    if not db.execute(text("SELECT 1 FROM departments WHERE id='d1'")):
        db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name) VALUES('d1','s1','Avd 1')"))
    db.commit()


def _client_superuser(app) -> FlaskClient:
    c = app.test_client()
    # Mark role/tenant via headers
    c.environ_base = {}
    return c


def test_access_control_and_listing():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_initial(db)
        finally:
            db.close()
    client = _client_superuser(app)
    # Superuser should see the page
    r = client.get("/ui/admin/system", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Systemadministration" in html
    assert "Arbetsplatser" in html
    # Non-superuser forbidden
    r_forbidden = client.get("/ui/admin/system", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert r_forbidden.status_code == 403


def test_create_site_and_department():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_initial(db)
        finally:
            db.close()
    client = _client_superuser(app)
    # Create site
    r = client.post("/ui/admin/system/site/create", data={"name": "Site 2"}, headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    assert r.status_code in (302, 303)
    # Verify site appears
    r = client.get("/ui/admin/system", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    html = r.data.decode("utf-8")
    assert "Site 2" in html
    # Create department on s1
    r = client.post("/ui/admin/system/department/create?site_id=s1", data={"name": "Avd 2"}, headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    assert r.status_code in (302, 303)
    r = client.get("/ui/admin/system?site_id=s1", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    html = r.data.decode("utf-8")
    assert "Avd 2" in html
