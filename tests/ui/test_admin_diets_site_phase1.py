from flask.testing import FlaskClient
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session


def _seed_site_and_diets(db):
    if not db.execute(text("SELECT 1 FROM sites WHERE id='s1'")).fetchone():
        db.execute(text("INSERT INTO sites(id,name) VALUES('s1','Site 1')"))
    # Seed via repo to ensure table exists
    from core.admin_repo import DietTypesRepo

    repo = DietTypesRepo()
    try:
        repo.create(site_id='s1', name="Gluten", default_select=False)
    except Exception:
        pass
    try:
        repo.create(site_id='s1', name="Laktos", default_select=False)
    except Exception:
        pass
    db.commit()


def test_access_and_listing_diets():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_site_and_diets(db)
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    with client.session_transaction() as s:
        s["site_id"] = "s1"
        s["role"] = "admin"
        s["tenant_id"] = 1
        s["user_id"] = "tester"
    # Admin can access diets page
    r = client.get("/ui/admin/diets?site_id=s1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Specialkosttyper" in html
    assert "Gluten" in html
    assert "Laktos" in html
    # Non-admin forbidden
    r_forbidden = client.get("/ui/admin/diets?site_id=s1", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert r_forbidden.status_code == 403


def test_create_diet_type():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_site_and_diets(db)
        finally:
            db.close()
    client = app.test_client()
    with client.session_transaction() as s:
        s["site_id"] = "s1"
        s["role"] = "admin"
        s["tenant_id"] = 1
        s["user_id"] = "tester"
    r = client.post(
        "/ui/admin/diets/create?site_id=s1",
        data={"name": "Nötfri"},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert r.status_code in (302, 303)
    r = client.get("/ui/admin/diets?site_id=s1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert "Nötfri" in r.data.decode("utf-8")
