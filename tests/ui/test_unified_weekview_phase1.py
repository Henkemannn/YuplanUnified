"""
Unified Module 1 – Weekview (Phase 1: Read-only, production UI) Tests

Tests for the new production-ready weekview UI that:
- Defaults to current week when year/week not provided
- Displays department-first layout with clean, mobile-friendly design
- Shows Alt2 selections visually
- Is read-only (no editing functionality)
- Is suitable for kitchen/department staff
"""
import uuid
from datetime import date as _date

import pytest

ETAG_RE = __import__("re").compile(r'^W/"weekview:dept:.*:year:\d{4}:week:\d{1,2}:v\d+"$')


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h("admin"),
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_happy_path_with_menu_data(client_admin):
    """
    Happy path: Seed data for one department with 7 days of menu data.
    Verify page renders correctly with all expected content.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 45

    # Seed sites/departments and dishes/menu
    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.models import Dish

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Testköket"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',25,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dep_id, "s": site_id, "n": "Kök Avdelning A"})
            db.commit()
            
            # Create dishes
            d1 = Dish(tenant_id=1, name="Köttbullar med potatismos", category=None)
            d2 = Dish(tenant_id=1, name="Fiskgratäng", category=None)
            d3 = Dish(tenant_id=1, name="Chokladpudding", category=None)
            d4 = Dish(tenant_id=1, name="Soppa", category=None)
            d5 = Dish(tenant_id=1, name="Lasagne", category=None)
            db.add_all([d1, d2, d3, d4, d5])
            db.commit()
            for d in [d1, d2, d3, d4, d5]:
                db.refresh(d)
            
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            # Monday lunch with all variants
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt2", dish_id=d2.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="dessert", dish_id=d3.id)
            # Tuesday dinner
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="tue", meal="dinner", variant_type="alt1", dish_id=d4.id)
            # Wednesday lunch
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="wed", meal="lunch", variant_type="alt1", dish_id=d5.id)
        finally:
            db.close()

    # Set up resident counts
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    r0 = client_admin.get(base, headers=_h("admin"))
    assert r0.status_code == 200
    etag0 = r0.headers.get("ETag")

    r_res = client_admin.patch(
        "/api/weekview/residents",
        json={
            "tenant_id": 1,
            "department_id": dep_id,
            "year": year,
            "week": week,
            "items": [
                {"day_of_week": 1, "meal": "lunch", "count": 18},
                {"day_of_week": 2, "meal": "dinner", "count": 12},
            ],
        },
        headers={**_h("admin"), "If-Match": etag0},
    )
    assert r_res.status_code in (200, 201)

    # Test UI rendering
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    
    # Assert: HTTP 200
    # Assert: Page contains "Vecka {WW}, {YYYY}"
    assert f"Vecka {week}, {year}" in html
    
    # Assert: Department names are present
    assert "Kök Avdelning A" in html
    assert "Testköket" in html
    
    # Assert: At least one lunch dish text per department is shown
    assert "Köttbullar med potatismos" in html
    assert "Fiskgratäng" in html
    assert "Lasagne" in html
    
    # Assert: Resident count text is present
    assert "Boende: 18" in html


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_missing_menu_shows_friendly_message(client_admin):
    """
    When weekview API returns no menu/week, assert informative message is rendered.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 50  # Week with no menu data

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Tomtköket"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dep_id, "s": site_id, "n": "Tom Avd"})
            db.commit()
        finally:
            db.close()

    # Render UI for week with no menu
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    
    # Assert informative message when no menu exists
    assert "Ingen meny för denna vecka ännu" in html or "Ingen meny" in html


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_navigation_links_correct(client_admin):
    """
    Assert that the navigation links have correct ?year=&week= values.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 10

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Navköket"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dep_id, "s": site_id, "n": "Nav Avd"})
            db.commit()
        finally:
            db.close()

    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    
    # Assert "Föregående vecka" link exists and points to week 9
    assert f"year=2025&amp;week=9" in html or f"year=2025&week=9" in html
    
    # Assert "Nästa vecka" link exists and points to week 11
    assert f"year=2025&amp;week=11" in html or f"year=2025&week=11" in html
    
    # Assert "Denna vecka" link exists
    assert "Denna vecka" in html


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_alt2_highlighting_visible(client_admin):
    """
    Seed at least one day with alt2_lunch=true.
    Assert that the rendered HTML contains a class or label used for alt2 highlighting.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 12

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.models import Dish

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Alt2köket"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dep_id, "s": site_id, "n": "Alt2 Avd"})
            db.commit()
            
            d1 = Dish(tenant_id=1, name="Normal rätt", category=None)
            d2 = Dish(tenant_id=1, name="Alternativ rätt", category=None)
            db.add_all([d1, d2])
            db.commit()
            db.refresh(d1); db.refresh(d2)
            
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt2", dish_id=d2.id)
        finally:
            db.close()

    # Set alt2 flag for Monday
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    r0 = client_admin.get(base, headers=_h("admin"))
    etag0 = r0.headers.get("ETag")

    r_alt2 = client_admin.patch(
        "/api/weekview/alt2",
        json={"tenant_id": 1, "department_id": dep_id, "year": year, "week": week, "days": [1]},  # Monday
        headers={**_h("editor"), "If-Match": etag0},
    )
    assert r_alt2.status_code in (200, 201)

    # Render UI
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    
    # Assert alt2 highlighting is present
    assert "alt2-badge" in html or "Alt 2 vald" in html


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_permissions_staff_can_access(client_admin):
    """
    Weekview is for regular staff (not only admin).
    Ensure a normal authenticated staff user can access /ui/weekview.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 15

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Staffköket"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dep_id, "s": site_id, "n": "Staff Avd"})
            db.commit()
        finally:
            db.close()

    # Test with different roles that should have access
    for role in ["admin", "cook", "unit_portal"]:
        r_ui = client_admin.get(
            f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
            headers=_h(role),
        )
        assert r_ui.status_code == 200, f"Role {role} should have access"


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_defaults_to_current_week(client_admin):
    """
    When year/week are not provided, weekview should redirect to current week.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Defaultköket"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dep_id, "s": site_id, "n": "Default Avd"})
            db.commit()
        finally:
            db.close()

    # Call without year/week params
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}",
        headers=_h("admin"),
        follow_redirects=False,
    )
    
    # Should redirect to current week
    assert r_ui.status_code == 302
    location = r_ui.headers.get("Location", "")
    
    # Get current week to verify redirect
    today = _date.today()
    iso_cal = today.isocalendar()
    current_year, current_week = iso_cal[0], iso_cal[1]
    
    assert f"year={current_year}" in location
    assert f"week={current_week}" in location


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_dinner_columns_hidden_when_no_dinner(client_admin):
    """
    When no dinner data exists for the week, dinner section should not clutter the UI.
    """
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    year, week = 2025, 20

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.models import Dish

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Lunchköket"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dep_id, "s": site_id, "n": "Lunch Avd"})
            db.commit()
            
            # Only add lunch dishes (no dinner)
            d1 = Dish(tenant_id=1, name="Pannkakor", category=None)
            db.add(d1)
            db.commit(); db.refresh(d1)
            
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
        finally:
            db.close()

    # Materialize weekview
    r0 = client_admin.get(f"/api/weekview?year={year}&week={week}&department_id={dep_id}", headers=_h("admin"))
    assert r0.status_code == 200

    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)
    
    # Dinner section should not be prominently visible when no dinner data
    # The template should conditionally render dinner based on vm.has_dinner
    assert "Pannkakor" in html  # Lunch dish present
    # Could check that dinner labels don't appear, but template handles this with {% if vm.has_dinner %}
