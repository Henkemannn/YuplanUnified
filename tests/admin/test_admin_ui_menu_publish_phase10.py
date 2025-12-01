"""Admin UI menu publish Phase 10 tests - Menu draft/published workflow."""
from __future__ import annotations

import pytest
from sqlalchemy import text


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def seeded_draft_week(app_session):
    """Seed database with test menu data for week 47/2025 with status='draft'."""
    from core.db import get_session
    
    db = get_session()
    try:
        # Clean first
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.execute(text("DELETE FROM dishes"))
        db.commit()
        
        # Create menu for week 47 with draft status
        db.execute(
            text("INSERT INTO menus (id, tenant_id, week, year, status) VALUES (:id, :tid, :week, :year, :status)"),
            {"id": 101, "tid": 1, "week": 47, "year": 2025, "status": "draft"}
        )
        
        # Create a dish
        db.execute(
            text("INSERT INTO dishes (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": 301, "tid": 1, "name": "Pasta carbonara"}
        )
        
        # Create menu variant
        db.execute(
            text("""
                INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                VALUES (:mid, :day, :meal, :vtype, :did)
            """),
            {"mid": 101, "day": "Måndag", "meal": "Lunch", "vtype": "alt1", "did": 301}
        )
        
        db.commit()
    finally:
        db.close()
    
    return app_session


def test_week_view_shows_draft_status(seeded_draft_week, client_admin):
    """Test that week view shows 'Utkast' status for draft menu."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/47",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for draft status indicator
    assert "Utkast" in html or "utkast" in html.lower()
    assert "Status:" in html or "status:" in html.lower()


def test_week_view_shows_publish_button_for_draft(seeded_draft_week, client_admin):
    """Test that draft menu shows 'Publicera vecka' button."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/47",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for publish button
    assert "Publicera vecka" in html
    assert "/ui/admin/menu-import/week/2025/47/publish" in html


def test_week_view_does_not_show_unpublish_button_for_draft(seeded_draft_week, client_admin):
    """Test that draft menu does not show unpublish button."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/47",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Should not have unpublish button
    assert "Återgå till utkast" not in html


def test_publish_changes_status_to_published(seeded_draft_week, client_admin):
    """Test POST /publish changes menu status from draft to published."""
    from core.db import get_session
    
    # Verify initial status is draft
    db = get_session()
    try:
        result = db.execute(
            text("SELECT status FROM menus WHERE id = :mid"),
            {"mid": 101}
        ).fetchone()
        assert result[0] == "draft"
    finally:
        db.close()
    
    # Get current ETag from week view
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    # Publish the menu with ETag
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/47/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value},
        follow_redirects=False
    )
    
    # Should redirect back to week view
    assert response.status_code == 302
    assert "/ui/admin/menu-import/week/2025/47" in response.location
    
    # Verify status changed to published
    db = get_session()
    try:
        result = db.execute(
            text("SELECT status FROM menus WHERE id = :mid"),
            {"mid": 101}
        ).fetchone()
        assert result[0] == "published"
    finally:
        db.close()


def test_publish_shows_success_message(seeded_draft_week, client_admin):
    """Test that publishing shows success flash message."""
    # Get current ETag from week view
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/47/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value},
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for success message
    assert "Vecka 47 publicerad" in html or "publicerad" in html.lower()


def test_published_menu_shows_published_status(seeded_draft_week, client_admin):
    """Test that published menu shows 'Publicerad' status."""
    # Get current ETag and publish the menu
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    client_admin.post(
        "/ui/admin/menu-import/week/2025/47/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value}
    )
    
    # Then view the week
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/47",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for published status
    assert "Publicerad" in html or "publicerad" in html.lower()


def test_published_menu_shows_unpublish_button(seeded_draft_week, client_admin):
    """Test that published menu shows 'Återgå till utkast' button."""
    # Get current ETag and publish the menu
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    client_admin.post(
        "/ui/admin/menu-import/week/2025/47/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value}
    )
    
    # View the week
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/47",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for unpublish button
    assert "Återgå till utkast" in html
    assert "/ui/admin/menu-import/week/2025/47/unpublish" in html


def test_published_menu_does_not_show_publish_button(seeded_draft_week, client_admin):
    """Test that published menu does not show publish button."""
    # Get current ETag and publish the menu
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    client_admin.post(
        "/ui/admin/menu-import/week/2025/47/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value}
    )
    
    # View the week
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/47",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Should not have publish button anymore
    assert "Publicera vecka" not in html or html.count("Publicera vecka") == 0


def test_unpublish_changes_status_to_draft(seeded_draft_week, client_admin):
    """Test POST /unpublish changes menu status from published back to draft."""
    from core.db import get_session
    
    # Get current ETag and publish first
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    client_admin.post(
        "/ui/admin/menu-import/week/2025/47/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value}
    )
    
    # Verify it's published
    db = get_session()
    try:
        result = db.execute(
            text("SELECT status FROM menus WHERE id = :mid"),
            {"mid": 101}
        ).fetchone()
        assert result[0] == "published"
    finally:
        db.close()
    
    # Get new ETag for unpublish
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    # Now unpublish with ETag
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/47/unpublish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value},
        follow_redirects=False
    )
    
    assert response.status_code == 302
    
    # Verify status changed back to draft
    db = get_session()
    try:
        result = db.execute(
            text("SELECT status FROM menus WHERE id = :mid"),
            {"mid": 101}
        ).fetchone()
        assert result[0] == "draft"
    finally:
        db.close()


def test_unpublish_shows_success_message(seeded_draft_week, client_admin):
    """Test that unpublishing shows success flash message."""
    # Get current ETag and publish first
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    client_admin.post(
        "/ui/admin/menu-import/week/2025/47/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value}
    )
    
    # Get new ETag for unpublish
    get_response = client_admin.get("/ui/admin/menu-import/week/2025/47", headers=ADMIN_HEADERS)
    etag_value = get_response.headers.get("ETag")
    
    # Unpublish with ETag
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/47/unpublish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag_value},
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for success message
    assert "satt till utkast" in html.lower() or "utkast" in html.lower()
