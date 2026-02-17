from flask.testing import FlaskClient
from sqlalchemy import text
import re

from core.app_factory import create_app
from core.db import get_session, get_new_session
from core.menu_service import MenuServiceDB
from core.models import Dish


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
        svc = MenuServiceDB()
        year = 2026
        week = 5
        menu = svc.create_or_get_menu(1, week, year)
        db2 = get_new_session()
        try:
            d1 = Dish(tenant_id=1, name="Alt1 Gryta", category=None)
            d2 = Dish(tenant_id=1, name="Alt2 Sallad", category=None)
            d3 = Dish(tenant_id=1, name="Dessert Frukt", category=None)
            d4 = Dish(tenant_id=1, name="Kvällsmat Soppa", category=None)
            db2.add_all([d1, d2, d3, d4])
            db2.commit()
            db2.refresh(d1)
            db2.refresh(d2)
            db2.refresh(d3)
            db2.refresh(d4)
        finally:
            db2.close()
        svc.set_variant(1, menu.id, "mon", "lunch", "main", d1.id)
        svc.set_variant(1, menu.id, "mon", "lunch", "alt2", d2.id)
        svc.set_variant(1, menu.id, "mon", "lunch", "dessert", d3.id)
        svc.set_variant(1, menu.id, "mon", "dinner", "main", d4.id)
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = "site-menu"
    rv = client.get(f"/ui/kitchen/menu?site_id=site-menu&year={year}&week={week}", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Menyöversikt" in html
    assert "Kvällsmat" in html
    assert "Dessert" in html
    assert "Alt 2" in html
    assert "yp-pill--alt2" in html
    assert re.search(r"app-shell__nav-item[^>]*>\s*Menyöversikt\s*<", html)
    assert 'app-shell__nav-item">Admin<' not in html
