"""
Test suite for Unified Admin Panel - Phase 1
Tests navigation shell, dashboard, permissions, and static assets.
"""

import pytest
import uuid
from datetime import date as _date, timedelta
from sqlalchemy import text


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
    assert "Översikt" in html
    assert "Idag" in html
    assert "data-testid=\"dashboard-today-card\"" in html
    assert "Menyval – kommande 4 veckor" in html
    assert "Kom ihåg att beställa" in html
    assert "Bockade rader visas i 2 dagar och rensas sedan automatiskt." in html
    assert "Veckostatus" not in html
    assert "Meny framåt" not in html
    assert "Kommunikation mellan avdelningar" not in html
    assert "Spara" not in html


def test_admin_dashboard_menu_choice_status_missing_week(client_admin):
    app = client_admin.application
    from core.db import get_session
    from core.week_key import build_week_key

    site_id = "site-menu"
    base = _date.today()
    week_keys = []
    menu_weeks = []
    for i in range(4):
        dt = base + timedelta(weeks=i)
        year, week, _ = dt.isocalendar()
        menu_weeks.append((int(year), int(week)))
        week_keys.append(build_week_key(int(year), int(week)))

    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT, resident_count_fixed INTEGER, version INTEGER)"))
            db.execute(
                text("INSERT OR REPLACE INTO sites(id,name,version) VALUES(:id,:name,0)"),
                {"id": site_id, "name": "TestSite"},
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) "
                    "VALUES('dep-a',:sid,'Avd A','fixed',0,0)"
                ),
                {"sid": site_id},
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) "
                    "VALUES('dep-b',:sid,'Avd B','fixed',0,0)"
                ),
                {"sid": site_id},
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS menus(id INTEGER PRIMARY KEY, tenant_id INTEGER, week INTEGER, year INTEGER, status TEXT, updated_at TEXT)"
                )
            )
            for year, week in menu_weeks:
                db.execute(
                    text("INSERT OR REPLACE INTO menus(id, tenant_id, year, week, status) VALUES(:id, 1, :y, :w, 'published')"),
                    {"id": int(f"{year}{week:02d}"), "y": year, "w": week},
                )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS menu_choice_completion(site_id TEXT NOT NULL, department_id TEXT NOT NULL, week_key TEXT NOT NULL, completed_at TEXT, UNIQUE(site_id, department_id, week_key))"
                )
            )
            for wk in week_keys:
                db.execute(
                    text(
                        "INSERT OR REPLACE INTO menu_choice_completion(site_id, department_id, week_key, completed_at) "
                        "VALUES(:sid, 'dep-a', :wk, '2026-01-01T00:00:00Z')"
                    ),
                    {"sid": site_id, "wk": wk},
                )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO menu_choice_completion(site_id, department_id, week_key, completed_at) "
                    "VALUES(:sid, 'dep-b', :wk, NULL)"
                ),
                {"sid": site_id, "wk": week_keys[0]},
            )
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["tenant_id"] = 1

    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Menyval – kommande 4 veckor" in html
    assert "1 avdelningar ligger inte i fas" in html
    assert "Visa avdelningar och saknade veckor" in html
    assert "avdelningar ligger inte i fas" in html


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
    
    assert 'class="app-shell__sidebar"' in html
    assert 'class="app-shell__nav"' in html
    assert "Översikt" in html
    assert "Veckovy" in html
    assert "Avdelningar" in html
    assert "Menyimport" in html
    assert "Specialkost" in html
    assert "Rapport / Statistik" in html


def test_admin_dashboard_quick_links_present(client_admin):
    """Test dashboard quick links are present."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert "Avdelningar" in html
    assert "Menyimport" in html
    assert "Specialkost" in html
    assert "Rapport" in html


def test_admin_dashboard_layout_structure(client_admin):
    """Test app shell layout structure exists."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert 'class="app-shell__page-header"' in html
    assert 'class="app-shell__grid"' in html
    assert 'class="app-shell__card"' in html


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
    """Test app shell CSS is linked."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert 'css/app_shell.css' in html
    assert 'unified_admin.css' not in html


def test_admin_dashboard_js_loaded(client_admin):
    """Test app shell JS is linked."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert 'js/app_shell.js' in html
    assert 'unified_admin.js' not in html


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
    assert "Veckovy" in html
    assert "/ui/weekview" in html

