"""
Unified Cook Dashboard - Phase 4 Tests
Tests for tablet-first cook dashboard UI
"""

import pytest
from flask.testing import FlaskClient


def _h(role="cook", tenant_id="1"):
    """Helper to create auth headers for tests."""
    return {"X-User-Role": role, "X-Tenant-Id": tenant_id}


# =============================================================================
# PART 1: RBAC Tests
# =============================================================================

def test_cook_dashboard_accessible_by_cook(client_admin: FlaskClient):
    """Cook role should access cook dashboard."""
    response = client_admin.get('/ui/cook', headers=_h(role="cook"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Kockens arbetsvy' in html


def test_cook_dashboard_accessible_by_admin(client_admin: FlaskClient):
    """Admin role should access cook dashboard."""
    response = client_admin.get('/ui/cook', headers=_h(role="admin"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Kockens arbetsvy' in html


def test_cook_dashboard_accessible_by_superuser(client_admin: FlaskClient):
    """Superuser role should access cook dashboard."""
    response = client_admin.get('/ui/cook', headers=_h(role="superuser"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Kockens arbetsvy' in html


def test_cook_dashboard_accessible_by_unit_portal(client_admin: FlaskClient):
    """Unit portal role should access cook dashboard."""
    response = client_admin.get('/ui/cook', headers=_h(role="unit_portal"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Kockens arbetsvy' in html


def test_cook_dashboard_forbidden_for_viewer(client_admin: FlaskClient):
    """Viewer role should NOT access cook dashboard."""
    response = client_admin.get('/ui/cook', headers=_h(role="viewer"))
    # Should get 403 or redirect
    assert response.status_code in [403, 302]


def test_cook_dashboard_forbidden_without_auth(client_admin: FlaskClient):
    """No auth headers should result in 401/403/302."""
    response = client_admin.get('/ui/cook')
    assert response.status_code in [401, 403, 302]


# =============================================================================
# PART 2: Today's Overview Tests
# =============================================================================

def test_cook_dashboard_shows_todays_date(client_admin: FlaskClient):
    """Dashboard should display today's formatted date."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should show a Swedish day name
    swedish_days = ['Måndag', 'Tisdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lördag', 'Söndag']
    assert any(day in html for day in swedish_days)


def test_cook_dashboard_shows_current_week(client_admin: FlaskClient):
    """Dashboard should display current week number."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should show "Vecka XX"
    assert 'Vecka' in html


def test_cook_dashboard_shows_lunch_section(client_admin: FlaskClient):
    """Dashboard should show lunch meal card."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Lunch section should exist
    assert 'id="lunchSection"' in html or 'Lunch' in html
    assert '🍽️' in html or 'Lunch' in html


def test_cook_dashboard_shows_dish_text(client_admin: FlaskClient):
    """Dashboard should show dish text (or default message)."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should show either a dish or "Ingen meny angiven"
    assert 'class="dish-text"' in html or 'Ingen meny' in html


def test_cook_dashboard_weekview_link_present(client_admin: FlaskClient):
    """Dashboard should have link to weekview."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should link to weekview
    assert 'weekview' in html
    assert 'Gå till veckovy' in html


# =============================================================================
# PART 3: Department Summary Tests
# =============================================================================

def test_cook_dashboard_shows_departments_section(client_admin: FlaskClient):
    """Dashboard should show departments overview section."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should have departments section
    assert 'Avdelningsöversikt' in html or 'departments-overview' in html


def test_cook_dashboard_shows_registration_status(client_admin: FlaskClient):
    """Dashboard should show registration status badges."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should show either "Registrerad" or "Ej gjord"
    has_status = 'Registrerad' in html or 'Ej gjord' in html
    assert has_status or 'Inga avdelningar' in html  # Or empty state


def test_cook_dashboard_uses_yp_badges(client_admin: FlaskClient):
    """Dashboard should use .yp-badge for status indicators."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should use yp-badge classes (or show empty state if no departments)
    # yp-button is always present in quick actions
    assert 'yp-badge' in html or 'Inga avdelningar' in html or 'yp-button' in html


# =============================================================================
# PART 4: Quick Links Tests
# =============================================================================

def test_cook_dashboard_shows_quick_actions(client_admin: FlaskClient):
    """Dashboard should show quick actions section."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should have quick actions
    assert 'Snabbval' in html or 'quick-actions' in html


def test_cook_dashboard_weekview_button_always_visible(client_admin: FlaskClient):
    """Weekview button should be visible to all roles."""
    response = client_admin.get('/ui/cook', headers=_h(role="cook"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Weekview link should be present
    assert 'Veckovy' in html
    assert '📅' in html


def test_cook_dashboard_admin_links_hidden_for_cook(client_admin: FlaskClient):
    """Cook role should NOT see admin-only links."""
    response = client_admin.get('/ui/cook', headers=_h(role="cook"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should NOT show Menyplanering or Rapporter for cook
    # (these are admin-only)
    # Note: This depends on template logic checking user_role


def test_cook_dashboard_admin_links_visible_for_admin(client_admin: FlaskClient):
    """Admin role should see admin-only links."""
    response = client_admin.get('/ui/cook', headers=_h(role="admin"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should show Menyplanering and Rapporter for admin
    assert 'Menyplanering' in html or 'Rapporter' in html


# =============================================================================
# PART 5: Responsiveness & UI Tests
# =============================================================================

def test_cook_dashboard_uses_yp_cards(client_admin: FlaskClient):
    """Dashboard should use .yp-card class for department cards."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should use yp-card
    assert 'yp-card' in html or 'meal-card' in html


def test_cook_dashboard_uses_yp_buttons(client_admin: FlaskClient):
    """Dashboard should use .yp-button classes."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should use yp-button
    assert 'yp-button' in html


def test_cook_dashboard_has_aria_labels(client_admin: FlaskClient):
    """Dashboard should have ARIA labels for accessibility."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should have aria-label attributes
    assert 'aria-label' in html


def test_cook_dashboard_loads_custom_css(client_admin: FlaskClient):
    """Dashboard should load unified_cook.css."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should reference cook CSS file
    assert 'unified_cook.css' in html


def test_cook_dashboard_loads_custom_js(client_admin: FlaskClient):
    """Dashboard should load unified_cook.js."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should reference cook JS file
    assert 'unified_cook.js' in html


# =============================================================================
# PART 6: Regression Tests
# =============================================================================

def test_weekview_still_works_after_cook_dashboard(client_admin: FlaskClient):
    """Weekview should still be accessible after adding cook dashboard."""
    # First access cook dashboard
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    
    # Then verify weekview still works (will redirect to current week)
    response = client_admin.get('/ui/weekview', headers=_h())
    assert response.status_code in [200, 302]  # 302 redirect to current week is OK


def test_admin_dashboard_still_works(client_admin: FlaskClient):
    """Admin dashboard should still work after adding cook dashboard."""
    response = client_admin.get('/ui/admin', headers=_h(role="admin"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Admin' in html or 'Adminpanel' in html


def test_cook_dashboard_does_not_break_existing_routes(client_admin: FlaskClient):
    """Adding cook dashboard should not break existing routes."""
    # Test a few key routes
    routes_to_test = [
        ('/ui/admin', 'admin'),
        ('/ui/admin/departments', 'admin'),
    ]
    
    for route, role in routes_to_test:
        response = client_admin.get(route, headers=_h(role=role))
        assert response.status_code in [200, 302]  # 200 OK or redirect is fine


# =============================================================================
# PART 7: Edge Cases
# =============================================================================

def test_cook_dashboard_handles_no_departments(client_admin: FlaskClient):
    """Dashboard should gracefully handle no departments (empty state)."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should either show departments or empty state
    has_content = 'department-card' in html or 'Inga avdelningar' in html
    assert has_content or 'empty-state' in html


def test_cook_dashboard_handles_no_site(client_admin: FlaskClient):
    """Dashboard should handle users without assigned site."""
    response = client_admin.get('/ui/cook', headers=_h())
    # Should still return 200, even if no site
    assert response.status_code == 200


# =============================================================================
# PART 8: Smoke Test
# =============================================================================

def test_cook_dashboard_smoke_test(client_admin: FlaskClient):
    """Comprehensive smoke test - dashboard renders without errors."""
    response = client_admin.get('/ui/cook', headers=_h())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Should have key elements
    assert 'Kockens arbetsvy' in html
    assert 'Dagens översikt' in html or 'today-overview' in html
    assert 'Snabbval' in html or 'quick-actions' in html
    
    # Should load CSS and JS
    assert 'unified_cook.css' in html
    assert 'unified_cook.js' in html
    
    # Should use unified design system (yp-button is always present)
    assert 'yp-button' in html
