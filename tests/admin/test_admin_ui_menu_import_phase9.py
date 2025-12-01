"""Admin UI menu import Phase 9 tests - Menu editing functionality."""
from __future__ import annotations

import pytest
from sqlalchemy import text


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def seeded_week_48(app_session):
    """Seed database with test menu data for week 48/2025."""
    from core.db import get_session
    
    db = get_session()
    try:
        # Clean first
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.execute(text("DELETE FROM dishes"))
        db.commit()
        
        # Create menu for week 48
        db.execute(
            text("INSERT INTO menus (id, tenant_id, week, year) VALUES (:id, :tid, :week, :year)"),
            {"id": 100, "tid": 1, "week": 48, "year": 2025}
        )
        
        # Create dishes
        dishes = [
            (201, 1, "Köttbullar med potatis"),
            (202, 1, "Fiskgratäng"),
            (203, 1, "Glass"),
            (204, 1, "Smörgåsar"),
        ]
        for dish_id, tenant_id, name in dishes:
            db.execute(
                text("INSERT INTO dishes (id, tenant_id, name) VALUES (:id, :tid, :name)"),
                {"id": dish_id, "tid": tenant_id, "name": name}
            )
        
        # Create menu variants for Monday
        variants = [
            (100, "Måndag", "Lunch", "alt1", 201),  # Köttbullar
            (100, "Måndag", "Lunch", "alt2", 202),  # Fiskgratäng
            (100, "Måndag", "Lunch", "dessert", 203),  # Glass
            (100, "Måndag", "Kväll", "kvall", 204),  # Smörgåsar
        ]
        for menu_id, day, meal, variant_type, dish_id in variants:
            db.execute(
                text("""
                    INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                    VALUES (:mid, :day, :meal, :vtype, :did)
                """),
                {"mid": menu_id, "day": day, "meal": meal, "vtype": variant_type, "did": dish_id}
            )
        
        db.commit()
    finally:
        db.close()
    
    return app_session


def test_get_edit_route_shows_input_fields(seeded_week_48, client_admin):
    """Test GET /edit route shows editable input fields with current dish names."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48/edit",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check page title and form
    assert "Redigera meny" in html
    assert "vecka 48" in html
    assert '<form' in html
    assert 'method="POST"' in html
    
    # Check that input fields exist with correct names
    assert 'name="Måndag_Lunch_alt1"' in html
    assert 'name="Måndag_Lunch_alt2"' in html
    assert 'name="Måndag_Lunch_dessert"' in html
    assert 'name="Måndag_Kväll_kvall"' in html
    
    # Check that current dishes are populated in value attributes
    assert "Köttbullar med potatis" in html
    assert "Fiskgratäng" in html
    assert "Glass" in html
    assert "Smörgåsar" in html


def test_get_edit_route_missing_menu_redirects(app_session, client_admin):
    """Test GET /edit for non-existent week redirects with warning."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/99/edit",
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Ingen meny hittades" in html


def test_post_save_updates_variant(seeded_week_48, client_admin):
    """Test POST /save updates a variant's dish text."""
    from core.db import get_session
    
    # Update Måndag Lunch Alt1 to new dish
    data = {
        "Måndag_Lunch_alt1": "Pasta carbonara",
        "Måndag_Lunch_alt2": "Fiskgratäng",  # Keep same
        "Måndag_Lunch_dessert": "Glass",  # Keep same
        "Måndag_Kväll_kvall": "Smörgåsar",  # Keep same
        # Other days can be empty
    }
    
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=data,
        headers=ADMIN_HEADERS,
        follow_redirects=False
    )
    
    # Should redirect to week view
    assert response.status_code == 302
    assert "/ui/admin/menu-import/week/2025/48" in response.location
    
    # Verify dish was updated in database
    db = get_session()
    try:
        result = db.execute(
            text("""
                SELECT d.name 
                FROM menu_variants mv
                JOIN dishes d ON mv.dish_id = d.id
                WHERE mv.menu_id = :mid 
                  AND mv.day = :day 
                  AND mv.meal = :meal 
                  AND mv.variant_type = :vtype
            """),
            {"mid": 100, "day": "Måndag", "meal": "Lunch", "vtype": "alt1"}
        ).fetchone()
        
        # Should have the updated dish name
        assert result is not None
        assert result[0] == "Pasta carbonara"
    finally:
        db.close()


def test_post_save_shows_success_message(seeded_week_48, client_admin):
    """Test POST /save shows success flash message."""
    data = {
        "Måndag_Lunch_alt1": "Updated dish",
    }
    
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=data,
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "uppdaterad" in html.lower() or "sparade" in html.lower()


def test_week_view_shows_updated_dish(seeded_week_48, client_admin):
    """Test that week view displays updated dish after save."""
    # First update the dish
    data = {
        "Måndag_Lunch_alt1": "Nytt rättnamn",
        "Måndag_Lunch_alt2": "Fiskgratäng",
        "Måndag_Lunch_dessert": "Glass",
        "Måndag_Kväll_kvall": "Smörgåsar",
    }
    
    client_admin.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=data,
        headers=ADMIN_HEADERS
    )
    
    # Then view the week
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Updated dish should appear
    assert "Nytt rättnamn" in html
    
    # Old dish should not appear
    assert "Köttbullar med potatis" not in html


def test_week_view_has_edit_button(seeded_week_48, client_admin):
    """Test that week view has 'Redigera meny' button."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for edit button
    assert "Redigera meny" in html
    assert "/ui/admin/menu-import/week/2025/48/edit" in html


def test_save_allows_empty_dishes(seeded_week_48, client_admin):
    """Test that empty dish values are allowed (removes dish)."""
    from core.db import get_session
    
    # Submit with empty alt1
    data = {
        "Måndag_Lunch_alt1": "",  # Empty - should remove dish
        "Måndag_Lunch_alt2": "Fiskgratäng",
        "Måndag_Lunch_dessert": "Glass",
        "Måndag_Kväll_kvall": "Smörgåsar",
    }
    
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=data,
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 302
    
    # Verify variant exists but has no dish
    db = get_session()
    try:
        result = db.execute(
            text("""
                SELECT dish_id 
                FROM menu_variants
                WHERE menu_id = :mid 
                  AND day = :day 
                  AND meal = :meal 
                  AND variant_type = :vtype
            """),
            {"mid": 100, "day": "Måndag", "meal": "Lunch", "vtype": "alt1"}
        ).fetchone()
        
        # dish_id should be NULL
        assert result is not None
        assert result[0] is None
    finally:
        db.close()


def test_save_trims_whitespace(seeded_week_48, client_admin):
    """Test that dish names are trimmed of leading/trailing whitespace."""
    from core.db import get_session
    
    # Submit with whitespace
    data = {
        "Måndag_Lunch_alt1": "   Pasta med sås   ",
    }
    
    client_admin.post(
        "/ui/admin/menu-import/week/2025/48/save",
        data=data,
        headers=ADMIN_HEADERS
    )
    
    # Verify trimmed
    db = get_session()
    try:
        result = db.execute(
            text("""
                SELECT d.name 
                FROM menu_variants mv
                JOIN dishes d ON mv.dish_id = d.id
                WHERE mv.menu_id = :mid 
                  AND mv.day = :day 
                  AND mv.meal = :meal 
                  AND mv.variant_type = :vtype
            """),
            {"mid": 100, "day": "Måndag", "meal": "Lunch", "vtype": "alt1"}
        ).fetchone()
        
        assert result is not None
        assert result[0] == "Pasta med sås"  # Trimmed
    finally:
        db.close()
