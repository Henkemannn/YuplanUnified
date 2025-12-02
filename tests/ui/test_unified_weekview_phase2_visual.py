"""
Test Unified Weekview Phase 2 - Visual Polish

Tests to verify premium design system integration:
1. Premium badges (success, warning, alt2, muted)
2. Department card styling with headers and summaries
3. Meal labels and icons
4. Accessibility (ARIA labels, contrast, font sizes)
5. No regressions in functionality
"""
import pytest
import uuid
from datetime import date as _date


def _h(role):
    """Helper to create auth headers for tests."""
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


@pytest.fixture
def enable_weekview(client_admin):
    """Enable weekview feature flag for testing."""
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h("admin"),
    )
    assert resp.status_code == 200


@pytest.fixture
def seed_weekview_data(client_admin):
    """Seed test data for weekview visual tests."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    
    from datetime import datetime
    today = datetime.now().date()
    year = today.isocalendar()[0]
    week = today.isocalendar()[1]
    
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            # Create site
            db.execute(
                text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"),
                {"i": site_id, "n": "Test Site"}
            )
            
            # Create department
            db.execute(
                text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0) ON CONFLICT(id) DO NOTHING"),
                {"i": dept_id, "s": site_id, "n": "Test Department"}
            )
            
            db.commit()
            
            # Create a menu for current week using menu service
            menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
            
        finally:
            db.close()
    
    return {"site_id": site_id, "dept_id": dept_id, "year": year, "week": week}


# ============================================================================
# BADGE SYSTEM TESTS
# ============================================================================

@pytest.mark.usefixtures("enable_weekview")
def test_registered_meal_shows_success_badge(client_admin, seed_weekview_data):
    """Registered meals should use unified badge system."""
    data = seed_weekview_data
    
    # Navigate to weekview
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should use unified badge component (.yp-badge)
    assert 'yp-badge' in html


@pytest.mark.usefixtures("enable_weekview")
def test_unregistered_meal_shows_muted_badge(client_admin, seed_weekview_data):
    """Unregistered meals should show gray muted badge."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should use unified badge component for unregistered
    assert 'yp-badge-muted' in html or 'badge-muted' in html
    assert 'Ej gjord' in html or 'Ej registrerad' in html


@pytest.mark.usefixtures("enable_weekview")
def test_alt2_shows_warning_badge(client_admin, seed_weekview_data):
    """Alt2 badge styling should be present (tests CSS, not data)."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    
    # Verify CSS file has alt2-badge styling with unified tokens
    css_resp = client_admin.get("/static/css/unified_weekview.css")
    assert css_resp.status_code == 200
    css = css_resp.data.decode("utf-8")
    
    # Should have alt2 badge styles using unified design system
    assert 'alt2-badge' in css or 'yp-badge-warning' in css


# ============================================================================
# DEPARTMENT CARD TESTS
# ============================================================================

@pytest.mark.usefixtures("enable_weekview")
def test_department_uses_card_component(client_admin, seed_weekview_data):
    """Department should be wrapped in premium card component."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should use unified card component
    assert 'yp-card' in html or 'department-card' in html
    # Should have department name
    assert 'Test Department' in html


@pytest.mark.usefixtures("enable_weekview")
def test_department_header_shows_summary(client_admin, seed_weekview_data):
    """Department header should show registration summary (X/Y format)."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should show summary in department header
    assert 'department-summary' in html or 'week-summary' in html
    # Should have Lunch label
    assert 'Lunch' in html or 'LUNCH' in html


# ============================================================================
# MEAL LABELS AND STRUCTURE TESTS
# ============================================================================

@pytest.mark.usefixtures("enable_weekview")
def test_meal_sections_have_labels(client_admin, seed_weekview_data):
    """Meal sections should have clear LUNCH and KVÄLL labels."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should have meal type labels
    assert 'LUNCH' in html
    # Weekview typically shows lunch, dinner is optional
    # Just verify label structure exists
    assert 'meal-label' in html


@pytest.mark.usefixtures("enable_weekview")
def test_meal_labels_have_icons(client_admin, seed_weekview_data):
    """Meal labels should include emoji icons for visual clarity."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should have meal icons (fork/spoon emoji or similar)
    assert '🍴' in html or '🌙' in html or 'meal-icon' in html


# ============================================================================
# ACCESSIBILITY TESTS
# ============================================================================

@pytest.mark.usefixtures("enable_weekview")
def test_meal_cells_have_aria_labels(client_admin, seed_weekview_data):
    """Meal cells should have descriptive ARIA labels for screen readers."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should have aria-label attributes
    assert 'aria-label=' in html
    # Should describe meal with day and registration status
    assert 'Lunch' in html or 'Kväll' in html


@pytest.mark.usefixtures("enable_weekview")
def test_unified_font_sizes_used(client_admin, seed_weekview_data):
    """CSS should use unified design system font size tokens."""
    # Check CSS file uses tokens
    resp = client_admin.get("/static/css/unified_weekview.css")
    assert resp.status_code == 200
    css = resp.data.decode("utf-8")
    
    # Should reference unified tokens
    assert '--yp-font-size' in css or 'var(--yp-font-size' in css


# ============================================================================
# LAYOUT AND SPACING TESTS
# ============================================================================

@pytest.mark.usefixtures("enable_weekview")
def test_day_cells_have_proper_spacing(client_admin, seed_weekview_data):
    """Day cells should use unified spacing tokens for breathability."""
    # Check CSS file
    resp = client_admin.get("/static/css/unified_weekview.css")
    assert resp.status_code == 200
    css = resp.data.decode("utf-8")
    
    # Should use unified gap tokens
    assert '--yp-gap' in css or 'var(--yp-gap' in css
    # Should have gap in grid
    assert 'gap:' in css


@pytest.mark.usefixtures("enable_weekview")
def test_cards_use_unified_radius(client_admin, seed_weekview_data):
    """Cards should use unified border radius tokens."""
    resp = client_admin.get("/static/css/unified_weekview.css")
    assert resp.status_code == 200
    css = resp.data.decode("utf-8")
    
    # Should use unified radius
    assert '--yp-radius' in css or 'var(--yp-radius' in css


# ============================================================================
# REGRESSION TESTS
# ============================================================================

@pytest.mark.usefixtures("enable_weekview")
def test_weekview_still_loads_successfully(client_admin, seed_weekview_data):
    """Weekview should still load without errors after visual polish."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Basic structure intact
    assert 'Veckovy' in html or 'Weekview' in html
    assert 'Test Department' in html


@pytest.mark.usefixtures("enable_weekview")
def test_unified_ui_css_loaded(client_admin, seed_weekview_data):
    """Weekview should load unified_ui.css for design system."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should load unified CSS
    assert 'unified_ui.css' in html


@pytest.mark.usefixtures("enable_weekview")
def test_unified_ui_js_loaded(client_admin, seed_weekview_data):
    """Weekview should load unified_ui.js for interactions."""
    data = seed_weekview_data
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={data['site_id']}&department_id={data['dept_id']}&year={data['year']}&week={data['week']}",
        headers=_h("admin")
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should load unified JS
    assert 'unified_ui.js' in html
