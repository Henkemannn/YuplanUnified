from flask.testing import FlaskClient
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session


def _seed_diet_type(db):
    # Seed via repo to ensure correct table
    from core.admin_repo import DietTypesRepo
    repo = DietTypesRepo()
    try:
        repo.create(tenant_id=1, name="Gluten", default_select=False)
    except Exception:
        pass


def test_nav_contains_systemadmin_link_for_superuser():
    app = create_app({"TESTING": True})
    client: FlaskClient = app.test_client()
    r = client.get("/ui/admin/system", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Systemadministration" in html
    assert "/ui/admin/system" in html


def test_diet_types_list_and_create_removed_from_systemadmin():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_diet_type(db)
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    # Systemadmin page should NOT include diet types anymore
    r = client.get("/ui/admin/system", headers={"X-User-Role": "superuser", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Specialkosttyper" not in html
    assert "Gluten" not in html
    # Diet management lives under site admin page
    r2 = client.get("/ui/admin/diets?site_id=s1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r2.status_code == 200
    h2 = r2.data.decode("utf-8")
    assert "Specialkosttyper" in h2
    # Create new type via site admin
    r3 = client.post("/ui/admin/diets/create?site_id=s1", data={"name": "Laktos"}, headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r3.status_code in (302, 303)
    r4 = client.get("/ui/admin/diets?site_id=s1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert "Laktos" in r4.data.decode("utf-8")
