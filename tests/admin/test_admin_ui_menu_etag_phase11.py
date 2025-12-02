"""Admin UI menu ETag Phase 11 tests - Optimistic locking for menu operations."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from sqlalchemy import text


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def seeded_menu_with_updated_at(app_session):
    """Seed database with test menu data including updated_at timestamp."""
    from core.db import get_session
    
    db = get_session()
    try:
        # Clean first
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.execute(text("DELETE FROM dishes"))
        db.commit()
        
        # Create menu for week 48/2025 with explicit updated_at
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO menus (id, tenant_id, week, year, status, updated_at) 
                VALUES (:id, :tid, :week, :year, :status, :updated_at)
            """),
            {"id": 102, "tid": 1, "week": 48, "year": 2025, "status": "draft", "updated_at": now}
        )
        
        # Create a dish
        db.execute(
            text("INSERT INTO dishes (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": 302, "tid": 1, "name": "Köttbullar"}
        )
        
        # Create menu variant
        db.execute(
            text("""
                INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                VALUES (:mid, :day, :meal, :vtype, :did)
            """),
            {"mid": 102, "day": "Måndag", "meal": "Lunch", "vtype": "alt1", "did": 302}
        )
        
        db.commit()
    finally:
        db.close()
    
    return app_session


def test_get_week_view_includes_etag_header(seeded_menu_with_updated_at):
    """Test that GET /week/<y>/<w> includes ETag in response headers."""
    client = seeded_menu_with_updated_at.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    assert "ETag" in response.headers
    etag = response.headers.get("ETag")
    assert etag.startswith('W/"menu-102-')
    

def test_get_edit_includes_etag_in_viewmodel(seeded_menu_with_updated_at):
    """Test that GET /edit includes ETag in template context."""
    client = seeded_menu_with_updated_at.test_client()
    
    response = client.get("/ui/admin/menu-import/week/2025/48/edit", headers=ADMIN_HEADERS)
    
    assert response.status_code == 200
    # Check that ETag hidden input exists
    assert b'name="_etag"' in response.data
    # Check that it has a value attribute (the ETag itself)
    assert b'value="W/' in response.data or b"value='W/" in response.data


def test_save_without_if_match_returns_412(seeded_menu_with_updated_at):
    """Test that POST /save without If-Match header returns 412 with ProblemDetails."""
    client = seeded_menu_with_updated_at.test_client()
    
    form_data = {
        "Måndag_Lunch_alt1": "Fiskgratäng",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    # Should redirect with flash message since it's not AJAX
    assert response.status_code == 302
    # Follow redirect to see flash message
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_save_with_wrong_etag_returns_412(seeded_menu_with_updated_at):
    """Test that POST /save with incorrect ETag returns 412."""
    client = seeded_menu_with_updated_at.test_client()
    
    # Use wrong ETag
    wrong_etag = 'W/"menu-102-1234567890000"'
    
    form_data = {
        "_etag": wrong_etag,
        "Måndag_Lunch_alt1": "Fiskgratäng",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_save_with_correct_etag_succeeds(seeded_menu_with_updated_at):
    """Test that POST /save with correct ETag succeeds."""
    client = seeded_menu_with_updated_at.test_client()
    
    # First get the current ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    form_data = {
        "_etag": etag,
        "Måndag_Lunch_alt1": "Fiskgratäng",
    }
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    # Follow redirect
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert b"Menyn uppdaterad" in response.data


def test_publish_without_etag_returns_412(seeded_menu_with_updated_at):
    """Test that POST /publish without ETag returns 412."""
    client = seeded_menu_with_updated_at.test_client()
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/publish",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_publish_with_correct_etag_succeeds(seeded_menu_with_updated_at):
    """Test that POST /publish with correct ETag succeeds."""
    client = seeded_menu_with_updated_at.test_client()
    
    # Get current ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/publish",
        data={"_etag": etag},
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"publicerad" in response.data


def test_unpublish_without_etag_returns_412(seeded_menu_with_updated_at):
    """Test that POST /unpublish without ETag returns 412."""
    client = seeded_menu_with_updated_at.test_client()
    
    # First publish the menu
    from core.db import get_session
    db = get_session()
    try:
        db.execute(
            text("UPDATE menus SET status='published' WHERE id=102")
        )
        db.commit()
    finally:
        db.close()
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/unpublish",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response.data


def test_unpublish_with_correct_etag_succeeds(seeded_menu_with_updated_at):
    """Test that POST /unpublish with correct ETag succeeds."""
    client = seeded_menu_with_updated_at.test_client()
    
    # First publish the menu
    from core.db import get_session
    db = get_session()
    try:
        db.execute(
            text("UPDATE menus SET status='published' WHERE id=102")
        )
        db.commit()
    finally:
        db.close()
    
    # Get current ETag
    get_response = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag = get_response.headers.get("ETag")
    
    response = client.post(
        "/ui/admin/menu-import/week/2025/48/unpublish",
        data={"_etag": etag},
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    response = client.get(response.location, headers=ADMIN_HEADERS)
    assert b"utkast" in response.data


def test_etag_changes_after_save(seeded_menu_with_updated_at):
    """Test that ETag value changes after a successful save operation."""
    client = seeded_menu_with_updated_at.test_client()
    
    # Get initial ETag
    response1 = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag1 = response1.headers.get("ETag")
    
    # Save changes
    form_data = {
        "_etag": etag1,
        "Måndag_Lunch_alt1": "Ny rätt",
    }
    
    response2 = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data,
        headers=ADMIN_HEADERS
    )
    
    assert response2.status_code == 302
    
    # Get new ETag
    response3 = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag2 = response3.headers.get("ETag")
    
    # ETags should be different
    assert etag1 != etag2


def test_concurrent_edit_scenario(seeded_menu_with_updated_at):
    """Test concurrent edit scenario where second save detects conflict."""
    client = seeded_menu_with_updated_at.test_client()
    
    # User A gets the page and ETag
    response_a = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag_a = response_a.headers.get("ETag")
    
    # User B gets the page and ETag (same ETag)
    response_b = client.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    etag_b = response_b.headers.get("ETag")
    
    assert etag_a == etag_b
    
    # User A saves first (succeeds)
    form_data_a = {
        "_etag": etag_a,
        "Måndag_Lunch_alt1": "User A's dish",
    }
    response_a_save = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data_a,
        headers=ADMIN_HEADERS
    )
    assert response_a_save.status_code == 302
    
    # User B tries to save with old ETag (fails)
    form_data_b = {
        "_etag": etag_b,  # This is now stale
        "Måndag_Lunch_alt1": "User B's dish",
    }
    response_b_save = client.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=form_data_b,
        headers=ADMIN_HEADERS
    )
    
    assert response_b_save.status_code == 302
    response_b_redirect = client.get(response_b_save.location, headers=ADMIN_HEADERS)
    assert b"Konflikt:" in response_b_redirect.data
