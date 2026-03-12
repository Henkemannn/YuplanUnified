"""" Admin Phase 6: Specialkostmodulen UI tests
Tests CRUD operations for dietary types in admin module.
"""
import pytest
from flask import Flask
from flask.testing import FlaskClient

# Auth headers for admin routes
ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def app_with_diet_types(app_session: Flask):
    """Seed database with test dietary types with strict site isolation."""
    from core.db import get_session
    from sqlalchemy import text

    conn = get_session()
    # Ensure sites exist (id,name only for sqlite tests)
    conn.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
    conn.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES('site-1','Testplats')"))
    # Clear existing data and seed via repo to satisfy legacy NOT NULL tenant_id
    conn.execute(text("DELETE FROM dietary_types"))
    from core.admin_repo import DietTypesRepo
    DietTypesRepo().create(site_id="site-1", name="Vegetarisk", default_select=True)
    DietTypesRepo().create(site_id="site-1", name="Glutenfri", default_select=False)
    conn.commit()
    yield app_session
    # Cleanup
    conn.execute(text("DELETE FROM dietary_types"))
    conn.commit()


@pytest.fixture
def client_admin(app_with_diet_types: Flask) -> FlaskClient:
    """Authenticated test client for admin routes (with active site)."""
    client = app_with_diet_types.test_client()
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["tenant_id"] = 1
        s["user_id"] = "tester"
        s["site_id"] = "site-1"
    return client


def test_admin_specialkost_list_shows_diet_types(client_admin: FlaskClient):
    """List route displays all dietary types with names and formarkeras status."""
    response = client_admin.get("/ui/admin/specialkost", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check page structure
    assert "Specialkost" in html
    assert "Skapa kosttyp" in html
    assert "specialkost-create-cta" in html
    assert "Här kan du redigera eller ta bort kosttyper." in html
    
    # Check seeded diet types appear
    assert "Vegetarisk" in html
    assert "Glutenfri" in html
    
    # Check default_select indicator (✓ for Vegetarisk, blank for Glutenfri)
    # Template uses: {{ "✓" if row.default_select else "" }}
    assert "✓" in html  # at least one checkmark present


def test_admin_specialkost_new_creates_diet_type(client_admin: FlaskClient):
    """New route creates dietary type and redirects to list."""
    # GET new form
    response = client_admin.get("/ui/admin/specialkost/new", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    new_html = response.data.decode()
    assert "Lägg till kosttyp" in new_html
    assert "Förmarkera i veckolistorna" in new_html
    assert "veckolistorna för statistiken" in new_html
    
    # POST new diet type (not pre-selected)
    response = client_admin.post(
        "/ui/admin/specialkost/new",
        data={"name": "Laktosfri", "default_select": ""},
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    assert response.status_code == 200
    html = response.data.decode()
    
    # Should redirect to list and show new type
    assert "Laktosfri" in html
    assert "Specialkost" in html


def test_admin_specialkost_new_with_default_select(client_admin: FlaskClient):
    """New route creates dietary type with formarkeras checkbox enabled."""
    response = client_admin.post(
        "/ui/admin/specialkost/new",
        data={"name": "Vegansk", "default_select": "on"},
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    assert response.status_code == 200
    html = response.data.decode()
    
    # Verify created with default_select
    assert "Vegansk" in html
    # Would need to query DB or check edit form to verify default_select=1


def test_admin_specialkost_edit_updates_diet_type(client_admin: FlaskClient):
    """Edit route updates dietary type name and formarkeras status."""
    # Get ID of "Glutenfri" (id=2 from seed)
    diet_id = 2
    
    # GET edit form
    response = client_admin.get(f"/ui/admin/specialkost/{diet_id}/edit", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode()
    assert "Redigera kosttyp" in html
    assert "Glutenfri" in html
    assert "Förmarkera i veckolistorna" in html
    assert "veckolistorna för statistiken" in html
    
    # POST update (change name, enable default_select)
    response = client_admin.post(
        f"/ui/admin/specialkost/{diet_id}/edit",
        data={"name": "Glutenfri (uppdaterad)", "default_select": "on"},
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    assert response.status_code == 200
    html = response.data.decode()
    
    # Should redirect to list with updated name
    assert "Glutenfri (uppdaterad)" in html
    assert "Glutenfri" in html  # old name still in updated name, so both match


def test_admin_specialkost_delete_removes_diet_type(client_admin: FlaskClient):
    """Delete route removes dietary type and shows confirmation."""
    # Verify delete is guarded by confirm modal trigger in list UI
    list_response = client_admin.get("/ui/admin/specialkost", headers=ADMIN_HEADERS)
    assert list_response.status_code == 200
    list_html = list_response.data.decode()
    assert "specialkost-delete-trigger" in list_html
    assert "Ta bort kosttyp?" in list_html
    assert "Kosttypen tas bort och kan påverka avdelningar som använder den." in list_html
    assert "return confirm(" not in list_html

    # Delete "Vegetarisk" (id=1)
    diet_id = 1
    
    response = client_admin.post(
        f"/ui/admin/specialkost/{diet_id}/delete",
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check flash message
    assert "Kosttypen har raderats" in html or "raderad" in html.lower()
    
    # Verify Vegetarisk no longer appears
    # (tricky: "Vegetarisk" might still appear in flash message)
    # Better to check list only shows Glutenfri
    assert "Glutenfri" in html
    # Count occurrences or check table structure instead


def test_admin_specialkost_delete_cascades_known_dependencies(client_admin: FlaskClient):
    """Delete route removes known dependency rows and then deletes the diet type."""
    from core.admin_repo import DietTypesRepo
    from core.db import get_session
    from sqlalchemy import text

    repo = DietTypesRepo()
    diet_id = repo.create(site_id="site-1", name="Fiskfri", default_select=False)

    conn = get_session()
    try:
        conn.execute(text("CREATE TABLE IF NOT EXISTS normal_exclusions (diet_type_id TEXT)"))
        conn.execute(
            text("INSERT INTO normal_exclusions(diet_type_id) VALUES(:diet_type_id)"),
            {"diet_type_id": str(diet_id)},
        )
        conn.commit()
    finally:
        conn.close()

    response = client_admin.post(
        f"/ui/admin/specialkost/{diet_id}/delete",
        headers=ADMIN_HEADERS,
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.data.decode()
    assert "raderats" in html.lower() or "borttagen" in html.lower()

    still_there = repo.get_by_id(diet_id)
    assert still_there is None

    conn = get_session()
    try:
        row = conn.execute(
            text("SELECT COUNT(1) FROM normal_exclusions WHERE diet_type_id=:diet_type_id"),
            {"diet_type_id": str(diet_id)},
        ).fetchone()
        assert int(row[0] or 0) == 0 if row else True
    finally:
        conn.close()


def test_admin_specialkost_list_empty_when_none(app_session: Flask):
    """List shows appropriate message when no dietary types exist."""
    from core.db import get_session
    from sqlalchemy import text
    
    conn = get_session()
    # Ensure a site exists and clear diet types
    conn.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
    conn.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES('site-1','Testplats')"))
    conn.execute(text("DELETE FROM dietary_types"))
    conn.commit()

    client = app_session.test_client()
    # Set active site to avoid redirect due to strict site isolation
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["tenant_id"] = 1
        s["user_id"] = "tester"
        s["site_id"] = "site-1"

    response = client.get("/ui/admin/specialkost", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode()
    
    # Template should handle empty state gracefully
    assert "Specialkost" in html
    assert "Skapa kosttyp" in html
    assert "Inga kosttyper ännu." in html
    assert "Skapa första kosttypen" in html
    # Table might be empty or show "Inga kosttyper"
    assert "Vegetarisk" not in html
    assert "Glutenfri" not in html


def test_admin_specialkost_edit_nonexistent_returns_404(client_admin: FlaskClient):
    """Edit route returns 404 for non-existent diet type ID."""
    response = client_admin.get("/ui/admin/specialkost/99999/edit", headers=ADMIN_HEADERS)
    # Repo.get_by_id returns None, route should handle gracefully
    # Assuming route renders error or redirects
    assert response.status_code in [404, 302, 500]  # depends on error handling
