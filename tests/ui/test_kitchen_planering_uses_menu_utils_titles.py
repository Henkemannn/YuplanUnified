import pytest
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session
from core.models import Dish

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site(db, site_id: str):
    db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER)"))
    db.execute(text("INSERT OR IGNORE INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "Test Site"})
    db.commit()


def test_planering_uses_menu_utils_titles_prefers_main_over_alt1():
    app = create_app()
    app.config.update({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            site_id = "site-canary"
            _seed_site(db, site_id)
            # Create two dishes: one for main, one for alt1
            main_dish = Dish(tenant_id=1, name="Main Köttkorv", category=None)
            alt1_dish = Dish(tenant_id=1, name="Alt1 Falukorv", category=None)
            db.add(main_dish)
            db.add(alt1_dish)
            db.commit()
            db.refresh(main_dish)
            db.refresh(alt1_dish)
            # Create or get menu for specific week/year and set Saturday lunch: main != alt1
            svc = app.menu_service  # type: ignore[attr-defined]
            menu = svc.create_or_get_menu(tenant_id=1, week=9, year=2026)
            svc.set_variant(tenant_id=1, menu_id=menu.id, day="sat", meal="lunch", variant_type="main", dish_id=main_dish.id)
            svc.set_variant(tenant_id=1, menu_id=menu.id, day="sat", meal="lunch", variant_type="alt1", dish_id=alt1_dish.id)
            svc.publish_menu(tenant_id=1, menu_id=menu.id)
        finally:
            db.close()
    client = app.test_client()
    # Ensure session has tenant/site context
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
    # Render Planera selected-state for Saturday lunch in same week/year
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year=2026&week=9&day=5&meal=lunch", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Assert Alt 1 banner shows the main dish
    assert "Main K\u00F6ttkorv" in html or "Main Köttkorv" in html
    # Assert Alt 1 input prefill uses the main dish text
    assert "class=\"alt-dish-input\"" in html
    assert "data-alt=\"1\"" in html
    assert "value=\"Main K\u00F6ttkorv\"" in html or "value=\"Main Köttkorv\"" in html
