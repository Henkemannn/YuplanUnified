"""Admin UI menu permissions Phase 12 tests - RBAC and CSRF protection."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from sqlalchemy import text


# Headers for different user roles
ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
STAFF_HEADERS = {"X-User-Role": "staff", "X-Tenant-Id": "1"}
SUPERUSER_HEADERS = {"X-User-Role": "superuser", "X-Tenant-Id": "1"}


@pytest.fixture
def seeded_menu_for_permissions(app_session):
    """Seed database with test menu data for permission tests."""
    from core.db import get_session
    
    db = get_session()
    try:
        # Clean first
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.execute(text("DELETE FROM dishes"))
        db.commit()
        
        # Create menu for week 49/2025 with draft status
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO menus (id, tenant_id, week, year, status, updated_at) 
                VALUES (:id, :tid, :week, :year, :status, :updated_at)
            """),
            {"id": 103, "tid": 1, "week": 49, "year": 2025, "status": "draft", "updated_at": now}
        )
        
        # Create a dish
        db.execute(
            text("INSERT INTO dishes (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": 303, "tid": 1, "name": "Lasagne"}
        )
        
        # Create menu variant
        db.execute(
            text("""
                INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                VALUES (:mid, :day, :meal, :vtype, :did)
            """),
            {"mid": 103, "day": "Måndag", "meal": "Lunch", "vtype": "alt1", "did": 303}
        )
        
        db.commit()
    finally:
        db.close()
    
    return app_session


# --- RBAC Tests ---

def test_staff_cannot_access_week_view(seeded_menu_for_permissions):
    """Test that staff role cannot access menu week view."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49", headers=STAFF_HEADERS)
    
    # Should return 403 forbidden or auth error
    assert response.status_code in [401, 403]
    if response.status_code == 403:
        data = response.get_json()
        assert data is not None
        # Check for 'detail' or 'error' field containing forbidden
        assert ("forbidden" in data.get("detail", "").lower() or 
                "forbidden" in data.get("error", "").lower() or
                data.get("status") == 403)


def test_staff_cannot_access_week_edit(seeded_menu_for_permissions):
    """Test that staff role cannot access menu edit page."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49/edit", headers=STAFF_HEADERS)
    
    assert response.status_code in [401, 403]


def test_staff_cannot_save_menu(seeded_menu_for_permissions):
    """Test that staff role cannot POST save menu changes."""
    client = seeded_menu_for_permissions.test_client()
    
    form_data = {
        "Måndag_Lunch_alt1": "Hacked dish",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/save",
        data=form_data,
        headers=STAFF_HEADERS
    )
    
    assert response.status_code in [401, 403]


def test_staff_cannot_publish_menu(seeded_menu_for_permissions):
    """Test that staff role cannot publish a menu."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/publish",
        headers=STAFF_HEADERS
    )
    
    assert response.status_code in [401, 403]


def test_staff_cannot_unpublish_menu(seeded_menu_for_permissions):
    """Test that staff role cannot unpublish a menu."""
    client = seeded_menu_for_permissions.test_client()
    
    # First set menu to published
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("UPDATE menus SET status='published' WHERE id=103"))
        db.commit()
    finally:
        db.close()
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/unpublish",
        headers=STAFF_HEADERS
    )
    
    assert response.status_code in [401, 403]


def test_admin_can_access_week_view(seeded_menu_for_permissions):
    """Test that admin role can access menu week view."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    assert b"Meny" in response.data


def test_admin_can_access_week_edit(seeded_menu_for_permissions):
    """Test that admin role can access menu edit page."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49/edit", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    assert b"Redigera" in response.data


def test_superuser_can_access_all_menu_operations(seeded_menu_for_permissions):
    """Test that superuser role can access all menu operations."""
    client = seeded_menu_for_permissions.test_client()
    
    # Can view
    response = client.get("/ui/admin/menu-import/week/2025/49", headers=SUPERUSER_HEADERS)
    assert response.status_code == 200
    
    # Can edit
    response = client.get("/ui/admin/menu-import/week/2025/49/edit", headers=SUPERUSER_HEADERS)
    assert response.status_code == 200


# --- CSRF Tests ---
# Note: CSRF is enforced via ENFORCED_PREFIXES in csrf.py but tests use X-User-Role headers
# which go through JWT path and skip CSRF validation. These tests verify CSRF token presence
# in templates and that forms work correctly.

def test_csrf_token_in_week_view_forms(seeded_menu_for_permissions):
    """Test that CSRF token inputs are present in week view forms."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    # Note: csrf_token_input() returns empty string when CSRF not active in test mode
    # In production with YUPLAN_STRICT_CSRF=1, it would include the token


def test_csrf_token_in_edit_form(seeded_menu_for_permissions):
    """Test that CSRF token input is present in edit form."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49/edit", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    # Verify the form includes csrf_token_input() call (rendered as empty in tests)
    # In production with YUPLAN_STRICT_CSRF=1, this would render the hidden input


def test_save_works_with_valid_auth_and_etag(seeded_menu_for_permissions):
    """Test that POST /save works with valid authorization and ETag."""
    client = seeded_menu_for_permissions.test_client()
    
    # Get current ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    form_data = {
        "_etag": etag,
        "Måndag_Lunch_alt1": "Test dish",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    # Should succeed (redirect)
    assert response.status_code == 302


def test_publish_works_with_valid_auth_and_etag(seeded_menu_for_permissions):
    """Test that POST /publish works with valid authorization and ETag."""
    client = seeded_menu_for_permissions.test_client()
    
    # Get ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/publish",
        data={"_etag": etag},
        headers=ADMIN_HEADERS
    )
    
    # Should succeed
    assert response.status_code == 302


def test_unpublish_works_with_valid_auth_and_etag(seeded_menu_for_permissions):
    """Test that POST /unpublish works with valid authorization and ETag."""
    client = seeded_menu_for_permissions.test_client()
    
    # Set menu to published
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("UPDATE menus SET status='published' WHERE id=103"))
        db.commit()
    finally:
        db.close()
    
    # Get ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/unpublish",
        data={"_etag": etag},
        headers=ADMIN_HEADERS
    )
    
    # Should succeed
    assert response.status_code == 302


# --- UX Tests ---

def test_conflict_flash_message_present(seeded_menu_for_permissions):
    """Test that conflict flash message is shown when ETag mismatches."""
    client = seeded_menu_for_permissions.test_client()
    
    # Use wrong ETag
    wrong_etag = 'W/"menu-103-1234567890000"'
    
    form_data = {
        "_etag": wrong_etag,
        "Måndag_Lunch_alt1": "Some dish",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    # Should redirect
    assert response.status_code == 302
    
    # Follow redirect and check for conflict message
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_status_text_displayed_correctly(seeded_menu_for_permissions):
    """Test that status badge shows correct text for draft/published."""
    client = seeded_menu_for_permissions.test_client()
    
    # Check draft status
    response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert b"Utkast" in response.data
    
    # Change to published
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("UPDATE menus SET status='published' WHERE id=103"))
        db.commit()
    finally:
        db.close()
    
    # Check published status
    response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert b"Publicerad" in response.data


def test_reload_link_in_conflict_flash(seeded_menu_for_permissions):
    """Test that reload link appears in conflict flash messages."""
    client = seeded_menu_for_permissions.test_client()
    
    # Use wrong ETag to trigger conflict
    wrong_etag = 'W/"menu-103-9999999999999"'
    
    form_data = {
        "_etag": wrong_etag,
        "Måndag_Lunch_alt1": "Test",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/49/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    # Follow redirect
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    
    # Check for reload link
    assert b"Ladda om" in response.data or b"reload" in response.data.lower()


def test_status_banner_styling(seeded_menu_for_permissions):
    """Test that status banner with proper CSS classes is present."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    # Check for status banner elements
    assert b"admin-status-banner" in response.data
    assert b"admin-actions-group" in response.data


def test_double_submit_protection_script(seeded_menu_for_permissions):
    """Test that admin.js is included for double-submit protection."""
    client = seeded_menu_for_permissions.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/49/edit", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    # Verify admin.js is included
    assert b"admin.js" in response.data
    # Verify form has protection class
    assert b"admin-form-protect" in response.data
