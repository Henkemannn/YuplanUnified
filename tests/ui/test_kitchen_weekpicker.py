from flask.testing import FlaskClient
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session


def _seed_site(db, site_id: str):
    if not db.execute(text("SELECT 1 FROM sites WHERE id=:i"), {"i": site_id}).fetchone():
        db.execute(text("INSERT INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": f"K3 {site_id}"})
        db.commit()


def test_kitchen_weekpicker_renders_on_pages():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed_site(db, "site-weekpicker")
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = "site-weekpicker"

    week_resp = client.get("/ui/kitchen/week?site_id=site-weekpicker&year=2026&week=5", headers=headers)
    assert week_resp.status_code == 200
    week_html = week_resp.data.decode("utf-8")
    assert "yp-weekpicker" in week_html
    assert "data-weekpicker-select" in week_html

    menu_resp = client.get("/ui/kitchen/menu?site_id=site-weekpicker&year=2026&week=5", headers=headers)
    assert menu_resp.status_code == 200
    menu_html = menu_resp.data.decode("utf-8")
    assert "yp-weekpicker" in menu_html
    assert "data-weekpicker-select" in menu_html
    assert "Välj vecka" not in menu_html
    assert ">Visa<" not in menu_html
