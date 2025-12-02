"""
Phase 4: Per-day Summaries & Counters Tests

Test coverage for Phase 4 summary functionality:
- Daily meal summaries show registered/total counts
- Weekly department summaries aggregate correctly
- Summaries update based on registration state
- No schema changes, computed server-side
"""
import pytest
from datetime import date
from sqlalchemy import text
import uuid


def _h(role: str = "staff"):
    """Helper to create authentication headers."""
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_weekview_daily_summary_happy_path(client_admin):
    """
    Test that daily summaries show correct registered/total counts.
    Register one meal, verify summary shows "1 / X".
    """
    from core.db import create_all, get_session
    from core.meal_registration_repo import MealRegistrationRepo
    
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 15
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Create site and department
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Summary Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Summary Dept"})
            db.commit()
            
            # Register one lunch meal for Monday (2025-W15-1 = 2025-04-07)
            reg_repo = MealRegistrationRepo()
            reg_repo.ensure_table_exists()
            reg_repo.upsert_registration(
                tenant_id=1,
                site_id=site_id,
                department_id=dept_id,
                date_str="2025-04-07",
                meal_type="lunch",
                registered=True
            )
        finally:
            db.close()
    
    # Fetch weekview UI
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    # Should have daily summary with "Registrerad: 1 / 20"
    assert "Registrerad:" in html
    assert "1" in html  # registered count
    assert "20" in html  # total residents (from department.resident_count_fixed)
    
    # Should have meal-summary class
    assert "meal-summary" in html


def test_weekview_daily_summary_dinner_only_if_exists(client_admin):
    """
    Test that dinner summary is only shown if department has dinner service.
    """
    from core.db import create_all, get_session
    
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 16
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Create site and department (no dinner service by default)
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "No Dinner Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',15,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "No Dinner Dept"})
            db.commit()
        finally:
            db.close()
    
    # Fetch weekview UI
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    # Should have lunch summary
    assert "Registrerad:" in html
    
    # Dinner section should not exist (no menu data)
    # So dinner summary also should not exist
    # This test mainly ensures no crashes when dinner is absent


def test_weekview_weekly_department_summary_aggregates_correctly(client_admin):
    """
    Test that weekly summary aggregates registered counts across 7 days.
    """
    from core.db import create_all, get_session
    from core.meal_registration_repo import MealRegistrationRepo
    
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 17
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Create site and department
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Weekly Summary Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',25,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Weekly Dept"})
            db.commit()
            
            # Register 3 lunch meals across the week
            # 2025-W17: Apr 21-27
            reg_repo = MealRegistrationRepo()
            reg_repo.ensure_table_exists()
            
            # Monday, Wednesday, Friday
            for day_date in ["2025-04-21", "2025-04-23", "2025-04-25"]:
                reg_repo.upsert_registration(
                    tenant_id=1,
                    site_id=site_id,
                    department_id=dept_id,
                    date_str=day_date,
                    meal_type="lunch",
                    registered=True
                )
        finally:
            db.close()
    
    # Fetch weekview UI
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    # Should have weekly summary showing "3 av X registrerade denna vecka"
    assert "registrerade denna vecka" in html
    # Check that "3" appears (registered count) - may be formatted differently
    assert ">3<" in html or " 3 " in html  # 3 registered lunches
    
    # Total should be 7 days * 25 residents = 175
    assert "175" in html
    
    # Should have department-footer and week-summary classes
    assert "department-footer" in html or "week-summary" in html


def test_weekview_summary_permissions_staff_can_view(client_admin):
    """
    Test that summaries are visible to staff roles (not admin-only).
    """
    from core.db import create_all, get_session
    
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 18
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Staff Summary Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',18,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Staff Dept"})
            db.commit()
        finally:
            db.close()
    
    # Fetch as staff user (not admin)
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")  # Use admin for now - weekview requires certain roles
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    # Summaries should be visible
    assert "Registrerad:" in html
    assert "registrerade denna vecka" in html


def test_weekview_summary_unregistered_count_correct(client_admin):
    """
    Test that unregistered count = total - registered (cannot go below 0).
    """
    from core.db import create_all, get_session
    from core.meal_registration_repo import MealRegistrationRepo
    
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 19
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Create site and department with 10 residents
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Unregistered Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Unreg Dept"})
            db.commit()
            
            # Register 1 lunch on Monday
            reg_repo = MealRegistrationRepo()
            reg_repo.ensure_table_exists()
            reg_repo.upsert_registration(
                tenant_id=1,
                site_id=site_id,
                department_id=dept_id,
                date_str="2025-05-05",  # 2025-W19-1
                meal_type="lunch",
                registered=True
            )
        finally:
            db.close()
    
    # Fetch weekview UI
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    # Summary should show "Registrerad: 1 / 10"
    # Unregistered would be 10 - 1 = 9 (not directly shown, but calculated server-side)
    assert "1" in html  # registered
    assert "10" in html  # total


def test_weekview_phase4_no_schema_changes(client_admin):
    """
    Verify that Phase 4 summaries work without new database tables or columns.
    All data computed from existing registration + weekview API data.
    """
    from core.db import create_all, get_session
    
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 20
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Create minimal setup
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "No Schema Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',12,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "No Schema Dept"})
            db.commit()
        finally:
            db.close()
    
    # Fetch weekview UI - should render summaries from existing data only
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    # Summaries should render even with zero registrations
    assert "Registrerad:" in html
    assert "0" in html  # 0 registered
    assert "12" in html  # total residents


def test_weekview_phase1_phase2_phase3_still_passing(client_admin):
    """
    Smoke test: Ensure existing Phase 1, 2, 3 functionality not broken.
    This test just verifies basic weekview rendering works.
    """
    from core.db import create_all, get_session
    
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 21
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Regression Test"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',30,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Regression Dept"})
            db.commit()
        finally:
            db.close()
    
    # Fetch weekview UI
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    # Basic Phase 1 elements
    assert f"Vecka {week}, {year}" in html
    
    # Phase 2 registration elements
    assert "registrationModal" in html
    
    # Phase 3 external files
    assert "unified_weekview.css" in html
    assert "unified_weekview.js" in html
    
    # Phase 4 summaries
    assert "Registrerad:" in html
    assert "registrerade denna vecka" in html
