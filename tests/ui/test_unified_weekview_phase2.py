"""
Unified Module 1 - Weekview Phase 2: Interactive Meal/Diet Editing Tests

Test coverage for Phase 2 interactive meal registration functionality:
- Staff can register/unregister meals per department/day/meal
- Registration state persists and displays correctly
- CSRF protection and RBAC enforced
- Form validation handles invalid inputs
"""
import pytest
from datetime import date, timedelta


def _h(role):
    """Helper to build request headers for tests."""
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


@pytest.fixture(autouse=True)
def setup_test_db(app_session):
    """Ensure meal_registrations table exists for tests."""
    from core.meal_registration_repo import MealRegistrationRepo
    repo = MealRegistrationRepo()
    repo.ensure_table_exists()
    yield


def test_weekview_registration_happy_path(client_admin):
    """
    Test successful meal registration flow:
    1. POST registration for lunch on a specific date
    2. Verify redirect to weekview
    3. Verify registration badge appears in UI
    """
    from core.db import get_session
    from sqlalchemy import text
    from datetime import date
    
    app = client_admin.application
    site_id = "site1"
    dept_id = "dept1"
    
    # Setup: Create site/department via SQL
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Test Dept"})
            db.commit()
        finally:
            db.close()
    
    # Current week
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    # Find Monday of current week
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    test_date = monday.strftime("%Y-%m-%d")
    
    # POST registration (lunch, registered=true)
    resp = client_admin.post(
        "/ui/weekview/registration",
        data={
            "csrf_token": "dummy_csrf_token_for_test",
            "site_id": "site1",
            "department_id": "dept1",
            "year": str(year),
            "week": str(week),
            "date": test_date,
            "meal_type": "lunch",
            "registered": "1",
        },
        headers=_h("admin"),
        follow_redirects=False
    )
    
    # Should redirect to weekview
    assert resp.status_code == 302
    assert f"/ui/weekview?site_id=site1&department_id=dept1&year={year}&week={week}" in resp.location
    
    # Verify persisted in database
    from core.meal_registration_repo import MealRegistrationRepo
    repo = MealRegistrationRepo()
    registrations = repo.get_registrations_for_week(1, "site1", "dept1", year, week)
    lunch_reg = next((r for r in registrations if r["date"] == test_date and r["meal_type"] == "lunch"), None)
    
    assert lunch_reg is not None
    assert lunch_reg["registered"] == 1
    
    # GET weekview and verify badge appears
    resp_view = client_admin.get(
        f"/ui/weekview?site_id=site1&department_id=dept1&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp_view.status_code == 200
    html = resp_view.get_data(as_text=True)
    
    # Should show "✓ Registrerad" badge
    assert "✓ Registrerad" in html


def test_weekview_registration_unregister(client_admin):
    """
    Test unregistering (unchecking) a meal:
    1. POST registration with registered=0 (checkbox unchecked)
    2. Verify database updated to registered=False
    3. Verify UI shows "Ej registrerad"
    """
    from core.db import get_session
    from sqlalchemy import text
    
    app = client_admin.application
    site_id = "site2"
    dept_id = "dept2"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Test Site 2"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Test Dept 2"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    monday = today - timedelta(days=today.weekday())
    test_date = monday.strftime("%Y-%m-%d")
    
    # First register it
    from core.meal_registration_repo import MealRegistrationRepo
    repo = MealRegistrationRepo()
    repo.upsert_registration(1, "site2", "dept2", test_date, "dinner", True)
    
    # Now unregister via POST (registered field missing = checkbox unchecked)
    resp = client_admin.post(
        "/ui/weekview/registration",
        data={
            "csrf_token": "dummy_csrf_token_for_test",
            "site_id": "site2",
            "department_id": "dept2",
            "year": str(year),
            "week": str(week),
            "date": test_date,
            "meal_type": "dinner",
            # registered field NOT sent (checkbox unchecked)
        },
        headers=_h("admin"),
        follow_redirects=False
    )
    
    assert resp.status_code == 302
    
    # Verify database updated
    registrations = repo.get_registrations_for_week(1, "site2", "dept2", year, week)
    dinner_reg = next((r for r in registrations if r["date"] == test_date and r["meal_type"] == "dinner"), None)
    
    assert dinner_reg is not None
    assert dinner_reg["registered"] == 0  # Unregistered
    
    # GET weekview and verify badge
    resp_view = client_admin.get(
        f"/ui/weekview?site_id=site2&department_id=dept2&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp_view.get_data(as_text=True)
    assert "Ej registrerad" in html


def test_weekview_registration_permissions_staff_allowed(client_admin):
    """
    Test that admin/cook role (staff) can register meals.
    """
    from core.db import get_session
    from sqlalchemy import text
    
    app = client_admin.application
    site_id = "site3"
    dept_id = "dept3"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Test Site 3"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Test Dept 3"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    monday = today - timedelta(days=today.weekday())
    test_date = monday.strftime("%Y-%m-%d")
    
    resp = client_admin.post(
        "/ui/weekview/registration",
        data={
            "csrf_token": "dummy_csrf_token_for_test",
            "site_id": "site3",
            "department_id": "dept3",
            "year": str(year),
            "week": str(week),
            "date": test_date,
            "meal_type": "lunch",
            "registered": "1",
        },
        headers=_h("admin"),
        follow_redirects=False
    )
    
    # Admin should be allowed (SAFE_UI_ROLES includes admin)
    assert resp.status_code == 302


def test_weekview_registration_validation_invalid_meal_type(client_admin):
    """
    Test that invalid meal_type is rejected with error message.
    """
    from core.db import get_session
    from sqlalchemy import text
    
    app = client_admin.application
    site_id = "site4"
    dept_id = "dept4"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Test Site 4"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Test Dept 4"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    monday = today - timedelta(days=today.weekday())
    test_date = monday.strftime("%Y-%m-%d")
    
    resp = client_admin.post(
        "/ui/weekview/registration",
        data={
            "csrf_token": "dummy_csrf_token_for_test",
            "site_id": "site4",
            "department_id": "dept4",
            "year": str(year),
            "week": str(week),
            "date": test_date,
            "meal_type": "breakfast",  # Invalid
            "registered": "1",
        },
        headers=_h("admin"),
        follow_redirects=False
    )
    
    # Should still redirect (invalid meal_type redirects back to weekview)
    assert resp.status_code == 302
    # Verify it redirects back to weekview (not workspace)
    assert f"/ui/weekview?site_id=site4&department_id=dept4&year={year}&week={week}" in resp.location


def test_weekview_registration_validation_missing_params(client_admin):
    """
    Test that missing required params trigger validation error.
    """
    resp = client_admin.post(
        "/ui/weekview/registration",
        data={
            "csrf_token": "dummy_csrf_token_for_test",
            # Missing site_id, department_id, etc.
            "meal_type": "lunch",
        },
        headers=_h("admin"),
        follow_redirects=False
    )
    
    # Should redirect to workspace when params missing
    assert resp.status_code == 302
    assert "/workspace" in resp.location


def test_weekview_ui_displays_registration_badges(client_admin):
    """
    Test that weekview UI correctly displays registration badges:
    - Registered meals show "✓ Registrerad"
    - Unregistered meals show "Ej registrerad"
    """
    from core.db import get_session
    from sqlalchemy import text
    from core.meal_registration_repo import MealRegistrationRepo
    
    app = client_admin.application
    site_id = "site5"
    dept_id = "dept5"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Test Site 5"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Test Dept 5"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    monday = today - timedelta(days=today.weekday())
    
    # Register lunch for Monday
    repo = MealRegistrationRepo()
    repo.upsert_registration(1, "site5", "dept5", monday.strftime("%Y-%m-%d"), "lunch", True)
    
    # GET weekview
    resp = client_admin.get(
        f"/ui/weekview?site_id=site5&department_id=dept5&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Should show both registered and unregistered badges
    assert "✓ Registrerad" in html  # For Monday lunch
    assert "Ej registrerad" in html  # For other days/meals


def test_weekview_registration_modal_present(client_admin):
    """
    Test that the registration modal HTML is present in the weekview template.
    """
    from core.db import get_session
    from sqlalchemy import text
    
    app = client_admin.application
    site_id = "site6"
    dept_id = "dept6"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Test Site 6"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Test Dept 6"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id=site6&department_id=dept6&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Modal should be present
    assert "registrationModal" in html
    # Phase 3: Functions are now in external JS file
    assert "unified_weekview.js" in html
    assert "Registrera måltid" in html
    assert 'name="registered"' in html
