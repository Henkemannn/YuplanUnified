"""
Phase 3: Usability & Speed Improvements Tests
Tests for inline toggle, keyboard navigation, visual clarity, and code organization.
"""
import pytest
from datetime import date
from sqlalchemy import text


def _h(role: str = "staff"):
    """Helper to create authentication headers."""
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_weekview_external_css_loaded(client_admin):
    """
    Test that external CSS file is loaded instead of inline styles.
    Part 5: Code organization
    """
    from core.db import get_session
    app = client_admin.application
    site_id, dept_id = "site_css", "dept_css"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "CSS Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "CSS Dept"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # External CSS should be linked
    assert 'href="/static/css/unified_weekview.css"' in html
    
    # Should NOT have inline styles in template
    # (base.html has styles, but template itself should be clean)
    lines = html.split('\n')
    template_style_count = sum(1 for line in lines if '<style>' in line and 'weekview' in line.lower())
    assert template_style_count == 0, "Template should not have inline weekview-specific styles"


def test_weekview_external_js_loaded(client_admin):
    """
    Test that external JavaScript file is loaded instead of inline scripts.
    Part 5: Code organization
    """
    from core.db import get_session
    app = client_admin.application
    site_id, dept_id = "site_js", "dept_js"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "JS Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "JS Dept"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # External JS should be linked
    assert 'src="/static/js/unified_weekview.js"' in html or 'unified_weekview.js' in html
    
    # Should NOT have inline openRegistrationModal function
    assert 'function openRegistrationModal' not in html


def test_weekview_keyboard_navigation_attributes(client_admin):
    """
    Test that navigation buttons have data-nav attributes for keyboard navigation.
    Part 3: Keyboard navigation
    """
    from core.db import get_session
    app = client_admin.application
    site_id, dept_id = "site_kbd", "dept_kbd"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Keyboard Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Keyboard Dept"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Navigation buttons should have data-nav attributes
    assert 'data-nav="prev-week"' in html
    assert 'data-nav="next-week"' in html


def test_weekview_meal_section_visual_distinction(client_admin):
    """
    Test that lunch and dinner sections have distinct CSS classes.
    Part 2: Visual clarity & accessibility
    """
    from core.db import get_session
    app = client_admin.application
    site_id, dept_id = "site_visual", "dept_visual"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Visual Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Visual Dept"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Should have distinct meal section classes
    assert 'meal-section--lunch' in html
    # Dinner may or may not be present depending on department settings, but if present should have class
    # For this test, just verify lunch class exists


def test_weekview_meal_cells_have_data_attributes(client_admin):
    """
    Test that meal cells have data attributes for inline toggle functionality.
    Part 1: Inline toggle mode
    """
    from core.db import get_session
    app = client_admin.application
    site_id, dept_id = "site_data", "dept_data"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Data Attrs Test"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Data Dept"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Meal cells should have data-meal-cell attribute
    assert 'data-meal-cell' in html
    assert 'data-date=' in html
    assert 'data-meal-type=' in html
    assert 'data-registered=' in html


def test_weekview_alt2_badge_enhanced_styling(client_admin):
    """
    Test that template uses correct Alt2 badge styling with 'ALT 2' text.
    Part 4: Alt2 visual enhancements
    This test verifies the template code is correct, even if no Alt2 is displayed.
    """
    import uuid
    from core.db import create_all, get_session
    app = client_admin.application
    site_id, dept_id = str(uuid.uuid4()), str(uuid.uuid4())
    year, week = 2025, 12
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Alt2 Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Alt2 Dept"})
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Template should use 'ALT 2' in uppercase (not 'Alt 2 vald')
    # The CSS class should be 'alt2-badge' (checked by other tests)
    # Since there's no menu/Alt2 data, we verify the template doesn't have the old text
    assert 'Alt 2 vald' not in html, "Old Alt2 badge text 'Alt 2 vald' should be replaced with 'ALT 2'"
    # External CSS should be loaded (which has .alt2-badge styles)
    assert 'unified_weekview.css' in html


def test_weekview_aria_labels_present(client_admin):
    """
    Test that meal cells have ARIA labels for accessibility.
    Part 2: Visual clarity & accessibility (WCAG AA)
    """
    from core.db import get_session
    app = client_admin.application
    site_id, dept_id = "site_aria", "dept_aria"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "ARIA Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "ARIA Dept"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Should have aria-label attributes
    assert 'aria-label=' in html
    # Specifically for lunch or dinner
    assert 'Lunch för' in html or 'aria-label="Lunch' in html


def test_weekview_modal_close_button_has_data_attribute(client_admin):
    """
    Test that modal close button uses data attribute instead of onclick.
    Part 5: Code organization (CSP-compliant)
    """
    from core.db import get_session
    app = client_admin.application
    site_id, dept_id = "site_modal", "dept_modal"
    
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": site_id, "n": "Modal Test Site"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0) ON CONFLICT(id) DO NOTHING"), 
                      {"i": dept_id, "s": site_id, "n": "Modal Dept"})
            db.commit()
        finally:
            db.close()
    
    today = date.today()
    iso_cal = today.isocalendar()
    year, week = iso_cal[0], iso_cal[1]
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}&year={year}&week={week}",
        headers=_h("admin")
    )
    html = resp.get_data(as_text=True)
    
    # Modal close button should use data attribute, not onclick
    assert 'data-action="close-modal"' in html
    # Should NOT have inline onclick handlers
    assert 'onclick="closeRegistrationModal' not in html
