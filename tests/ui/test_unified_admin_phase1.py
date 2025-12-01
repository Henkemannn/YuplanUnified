"""
Test suite for Unified Admin Panel - Phase 1
Tests navigation shell, dashboard, permissions, and static assets.
"""

import pytest
import uuid
from datetime import date as _date


def _h(role):
    """Helper to create auth headers for tests."""
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


# ============================================================================
# Admin Dashboard Route Tests
# ============================================================================

def test_admin_dashboard_happy_path_admin(client_admin):
    """Test admin user can access admin dashboard."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Adminpanel" in html
    assert "Välkommen till Adminpanelen" in html


def test_admin_dashboard_happy_path_superuser(client_superuser):
    """Test superuser can access admin dashboard."""
    resp = client_superuser.get("/ui/admin", headers=_h("superuser"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Adminpanel" in html
    assert "Översikt" in html


def test_admin_dashboard_permissions_editor_denied(client_user):
    """Test staff (editor) cannot access admin dashboard."""
    resp = client_user.get("/ui/admin", headers=_h("editor"))
    
    # Should get 403 Forbidden
    assert resp.status_code == 403


def test_admin_dashboard_permissions_viewer_denied(client_user):
    """Test viewer role cannot access admin dashboard."""
    resp = client_user.get("/ui/admin", headers=_h("viewer"))
    
    # Should get 403 Forbidden
    assert resp.status_code == 403


def test_admin_dashboard_permissions_cook_denied(client_user):
    """Test cook (app role) cannot access admin dashboard."""
    resp = client_user.get("/ui/admin", headers=_h("cook"))
    
    # Should get 403 Forbidden (cook maps to viewer)
    assert resp.status_code == 403


def test_admin_dashboard_permissions_unit_portal_denied(client_user):
    """Test unit_portal (app role) cannot access admin dashboard."""
    resp = client_user.get("/ui/admin", headers=_h("unit_portal"))
    
    # Should get 403 Forbidden (unit_portal maps to editor)
    assert resp.status_code == 403


# ============================================================================
# Template & Layout Tests
# ============================================================================

def test_admin_dashboard_sidebar_present(client_admin):
    """Test sidebar navigation is present."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert 'class="admin-sidebar"' in html
    assert 'class="sidebar-nav"' in html
    assert "Översikt" in html  # Dashboard link
    assert "Menyimport" in html
    assert "Avdelningar" in html
    assert "Användare" in html
    assert "Rapporter" in html
    assert "Inställningar" in html
    assert "Tillbaka till Veckovy" in html


def test_admin_dashboard_quick_links_present(client_admin):
    """Test all 6 quick link cards are present."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert 'class="quick-links-grid"' in html
    assert 'class="quick-link-card"' in html
    
    # Check all 6 cards
    assert "Menyimport & Veckomeny" in html
    assert "Avdelningar" in html
    assert "Användare" in html
    assert "Rapporter" in html
    assert "Inställningar" in html
    assert "Tillbaka till Veckovy" in html


def test_admin_dashboard_flash_area_present(client_admin):
    """Test flash message area exists."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    # Flash container should be in the template structure
    assert 'class="content-header"' in html
    assert 'class="page-content"' in html


def test_admin_dashboard_current_week_displayed(client_admin):
    """Test current week badge is displayed."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    # Should show current week
    assert "Vecka" in html
    # Week number should be present (1-53)
    import re
    assert re.search(r'Vecka\s+\d+', html)


# ============================================================================
# Static Assets Tests
# ============================================================================

def test_admin_dashboard_css_loaded(client_admin):
    """Test unified_admin.css is linked."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert 'unified_admin.css' in html


def test_admin_dashboard_js_loaded(client_admin):
    """Test unified_admin.js is linked."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert 'unified_admin.js' in html


# ============================================================================
# Navigation Links Tests
# ============================================================================

def test_admin_navigation_link_visible_to_admin(client_admin):
    """Test admin sees admin link in weekview."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())

    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name) VALUES ('{site_id}', 'TestSite')"))
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"
                ),
                {"i": dep_id, "s": site_id, "n": "TestDep"}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}",
        headers=_h("admin"),
        follow_redirects=True  # Follow redirect to get final page
    )
    html = resp.data.decode("utf-8")
    
    # Should have admin button
    assert "Admin" in html
    assert "/ui/admin" in html


def test_admin_navigation_link_visible_to_superuser(client_superuser):
    """Test superuser sees admin link in weekview."""
    app = client_superuser.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())

    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name) VALUES ('{site_id}', 'TestSite')"))
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"
                ),
                {"i": dep_id, "s": site_id, "n": "TestDep"}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_superuser.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}",
        headers=_h("superuser"),
        follow_redirects=True  # Follow redirect to get final page
    )
    html = resp.data.decode("utf-8")
    
    # Should have admin button
    assert "Admin" in html
    assert "/ui/admin" in html


def test_admin_navigation_link_hidden_from_staff(client_user):
    """Test staff (editor) doesn't see admin link in weekview."""
    app = client_user.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())

    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name) VALUES ('{site_id}', 'TestSite')"))
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"
                ),
                {"i": dep_id, "s": site_id, "n": "TestDep"}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_user.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}",
        headers=_h("editor")
    )
    html = resp.data.decode("utf-8")
    
    # Should NOT have admin button
    assert '⚙️ Admin' not in html


def test_weekview_link_in_admin_sidebar(client_admin):
    """Test admin sidebar has link back to weekview."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    # Should have weekview link in sidebar
    assert "Tillbaka till Veckovy" in html
    assert "/ui/weekview" in html

