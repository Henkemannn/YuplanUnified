"""Admin UI menu import Phase 9 tests - Menu editing functionality."""
from __future__ import annotations

import pytest
import re
from sqlalchemy import text


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def client_admin(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = "site-import-9"
    return client


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
        
        db.execute(
            text("INSERT OR REPLACE INTO sites (id, name, tenant_id, version) VALUES (:id, :name, :tid, 0)"),
            {"id": "site-import-9", "name": "Site Import 9", "tid": 1},
        )

        # Create menu for week 48
        db.execute(
            text("INSERT INTO menus (id, tenant_id, site_id, week, year, status) VALUES (:id, :tid, :sid, :week, :year, :status)"),
            {"id": 100, "tid": 1, "sid": "site-import-9", "week": 48, "year": 2025, "status": "draft"}
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


@pytest.fixture
def client_admin_imported(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = "site-import-11"
    return client


@pytest.fixture
def seeded_imported_week_11(app_session):
    """Seed importer-like keys (monday/lunch/main + dinner/main) for regression coverage."""
    from core.db import get_session

    db = get_session()
    try:
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.execute(text("DELETE FROM dishes"))
        db.commit()

        db.execute(
            text("INSERT OR REPLACE INTO sites (id, name, tenant_id, version) VALUES (:id, :name, :tid, 0)"),
            {"id": "site-import-11", "name": "Site Import 11", "tid": 1},
        )

        db.execute(
            text("INSERT INTO menus (id, tenant_id, site_id, week, year, status) VALUES (:id, :tid, :sid, :week, :year, :status)"),
            {"id": 111, "tid": 1, "sid": "site-import-11", "week": 11, "year": 2026, "status": "draft"},
        )

        dishes = [
            (401, 1, "Lasagne"),
            (402, 1, "Fiskgryta"),
            (403, 1, "Chokladpudding"),
            (404, 1, "Köttsoppa"),
        ]
        for dish_id, tenant_id, name in dishes:
            db.execute(
                text("INSERT INTO dishes (id, tenant_id, name) VALUES (:id, :tid, :name)"),
                {"id": dish_id, "tid": tenant_id, "name": name},
            )

        # Importer-style keys: english day/meal with 'main' variant.
        variants = [
            (111, "monday", "lunch", "main", 401),
            (111, "monday", "lunch", "alt2", 402),
            (111, "monday", "lunch", "dessert", 403),
            (111, "monday", "dinner", "main", 404),
        ]
        for menu_id, day, meal, variant_type, dish_id in variants:
            db.execute(
                text(
                    """
                    INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                    VALUES (:mid, :day, :meal, :vtype, :did)
                    """
                ),
                {"mid": menu_id, "day": day, "meal": meal, "vtype": variant_type, "did": dish_id},
            )

        db.commit()
    finally:
        db.close()

    return app_session


@pytest.fixture
def seeded_week_nav_cross_year(app_session):
    """Seed three imported weeks across year boundary for week-nav assertions."""
    from core.db import get_session

    db = get_session()
    try:
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.execute(text("DELETE FROM dishes"))
        db.commit()

        db.execute(
            text("INSERT OR REPLACE INTO sites (id, name, tenant_id, version) VALUES (:id, :name, :tid, 0)"),
            {"id": "site-import-nav", "name": "Site Import Nav", "tid": 1},
        )

        menus = [
            (151, 1, "site-import-nav", 52, 2025, "draft"),
            (152, 1, "site-import-nav", 1, 2026, "draft"),
            (153, 1, "site-import-nav", 2, 2026, "published"),
        ]
        for menu_id, tid, sid, week, year, status in menus:
            db.execute(
                text(
                    "INSERT INTO menus (id, tenant_id, site_id, week, year, status) VALUES (:id, :tid, :sid, :week, :year, :status)"
                ),
                {"id": menu_id, "tid": tid, "sid": sid, "week": week, "year": year, "status": status},
            )

        db.execute(
            text("INSERT INTO dishes (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": 451, "tid": 1, "name": "Nav rätt"},
        )

        for menu_id in [151, 152, 153]:
            db.execute(
                text(
                    """
                    INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                    VALUES (:mid, :day, :meal, :vtype, :did)
                    """
                ),
                {"mid": menu_id, "day": "monday", "meal": "lunch", "vtype": "main", "did": 451},
            )

        db.commit()
    finally:
        db.close()

    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = "site-import-nav"
    return client


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


def test_edit_route_uses_app_shell_cards_and_primary_save(seeded_week_48, client_admin):
    """Edit page should use app-shell card UI hooks and single primary save action."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48/edit",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # App-shell migration hooks
    assert 'class="app-shell__card menu-editor-card menu-editor-card--status"' in html
    assert 'data-menu-editor-edit="1"' in html
    assert 'menu-editor-day-card' in html

    # Single save action semantics
    assert '>Spara<' in html
    assert 'class="yp-btn yp-btn-primary"' in html

    # Legacy inline white style block should be gone
    assert '<style>' not in html
    assert 'background-color: #f5f5f5' not in html


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
    assert "Sparat ✓" in html


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
    """Test that week view has 'Redigera' button."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48",
        headers=ADMIN_HEADERS
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Check for edit button
    assert "Redigera" in html
    assert "/ui/admin/menu-import/week/2025/48?edit=1" in html
    assert "/ui/admin/menu-import/week/2025/48/edit" not in html


def test_week_view_read_only_default_has_no_inputs_and_swedish_labels(seeded_week_48, client_admin):
    """Default week page should be read-only with Swedish labels and no input fields."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "Meny - vecka 48/2025" in html
    assert "Veckomeny" in html
    assert "Måndag" in html
    assert "Lördag" in html
    assert "Söndag" in html
    assert "menu-day-row" in html
    assert 'name="Måndag_Lunch_alt1"' not in html
    assert "menu-editor-input" not in html


def test_week_view_edit_mode_shows_inputs_save_and_cancel(seeded_week_48, client_admin):
    """Edit mode should render editable fields and save/cancel actions on same route."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48?edit=1",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert 'name="Måndag_Lunch_alt1"' in html
    assert 'name="Måndag_Lunch_alt2"' in html
    assert 'name="Måndag_Lunch_dessert"' in html
    assert 'name="Måndag_Kväll_kvall"' in html
    assert ">Spara<" in html
    assert "Avbryt" in html
    assert "/ui/admin/menu-import/week/2025/48/save" in html
    assert 'href="/ui/admin/menu-import/week/2025/48"' in html
    assert "/ui/admin/menu-import/week/2025/48/edit" not in html


def test_week_view_edit_mode_has_tight_day_row_grid_selectors(seeded_week_48, client_admin):
    """Edit mode should render row hooks for tight label/input grid layout."""
    response = client_admin.get(
        "/ui/admin/menu-import/week/2025/48?edit=1",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "menu-day-row" in html
    assert "menu-editor-edit-row" in html
    assert "menu-editor-meal-type" in html
    assert "menu-editor-input" in html


def test_post_save_from_edit_mode_redirects_to_read_only_with_success_banner(seeded_week_48, client_admin):
    """Saving from edit mode should redirect back to read-only week page with success banner."""
    response = client_admin.post(
        "/ui/admin/menu-import/week/2025/48/save?edit=1",
        data={
            "Måndag_Lunch_alt1": "Pyttipanna",
            "Måndag_Lunch_alt2": "Fiskgratäng",
            "Måndag_Lunch_dessert": "Glass",
            "Måndag_Kväll_kvall": "Smörgåsar",
        },
        headers=ADMIN_HEADERS,
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "Sparat ✓" in html
    assert 'name="Måndag_Lunch_alt1"' not in html
    assert "/ui/admin/menu-import/week/2025/48?edit=1" in html


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


def test_week_view_renders_imported_dishes_for_2026_w11(seeded_imported_week_11, client_admin_imported):
    """Read-only week view should render imported dish names (not only placeholder dashes)."""
    response = client_admin_imported.get(
        "/ui/admin/menu-import/week/2026/11",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "Veckomeny" in html
    assert "Måndag" in html
    assert "Lunch alt 1" in html
    assert "Lunch alt 2" in html
    assert "Dessert" in html
    assert "Middag" in html
    assert "Lasagne" in html
    assert "Fiskgryta" in html
    assert "Chokladpudding" in html
    assert "Köttsoppa" in html


def test_week_view_edit_mode_prefills_imported_values_for_2026_w11(seeded_imported_week_11, client_admin_imported):
    """Edit mode should prefill inputs with existing imported values for same week route."""
    response = client_admin_imported.get(
        "/ui/admin/menu-import/week/2026/11?edit=1",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert 'name="Måndag_Lunch_alt1"' in html
    assert 'value="Lasagne"' in html
    assert 'name="Måndag_Kväll_kvall"' in html
    assert 'value="Köttsoppa"' in html
    assert "/ui/admin/menu-import/week/2026/11/edit" not in html


def test_week_picker_shows_cross_year_options_and_status_chips(seeded_week_nav_cross_year):
    """Picker should render imported cross-year week options with status chips."""
    response = seeded_week_nav_cross_year.get(
        "/ui/admin/menu-import/week/2026/1",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert 'data-testid="menu-week-picker"' in html
    assert 'id="menu-week-picker-dropdown"' in html
    assert "Vecka 1 / 2026" in html
    assert 'data-url="/ui/admin/menu-import/week/2025/52"' in html
    assert 'data-url="/ui/admin/menu-import/week/2026/1"' in html
    assert 'data-url="/ui/admin/menu-import/week/2026/2"' in html
    assert "PUBLICERAD" in html
    assert "UTKAST" in html


def test_week_nav_disables_left_on_first_imported_week(seeded_week_nav_cross_year):
    """First imported week should disable previous-arrow and keep next-arrow enabled."""
    response = seeded_week_nav_cross_year.get(
        "/ui/admin/menu-import/week/2025/52",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert re.search(r'data-week-nav="prev"[^>]*disabled', html)
    assert re.search(r'data-week-nav="next"(?![^>]*disabled)', html)


def test_week_nav_disables_right_on_last_imported_week(seeded_week_nav_cross_year):
    """Last imported week should disable next-arrow and keep previous-arrow enabled."""
    response = seeded_week_nav_cross_year.get(
        "/ui/admin/menu-import/week/2026/2",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert re.search(r'data-week-nav="next"[^>]*disabled', html)
    assert re.search(r'data-week-nav="prev"(?![^>]*disabled)', html)
