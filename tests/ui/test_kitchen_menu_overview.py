from flask.testing import FlaskClient
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session


def _seed_site(db, site_id: str):
    if not db.execute(text("SELECT 1 FROM sites WHERE id=:i"), {"i": site_id}).fetchone():
        db.execute(text("INSERT INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": f"K3 {site_id}"})
        db.commit()


def test_kitchen_menu_overview_renders():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_site(db, "site-menu")
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = "site-menu"
    rv = client.get("/ui/kitchen/menu?site_id=site-menu", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Menyöversikt" in html
