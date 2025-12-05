"""
Admin Phase 7: Menu Import UI tests (MVP)
Tests basic menu import functionality and week view display.
"""
import pytest
from flask import Flask
from flask.testing import FlaskClient
from io import BytesIO

# Auth headers for admin routes
ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def app_with_menu(app_session: Flask):
    """Seed database with test menu data for week 48/2025."""
    from core.db import get_session
    from sqlalchemy import text
    from core.models import Menu, Dish, MenuVariant
    
    conn = get_session()
    # Ensure tables exist
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            week INTEGER NOT NULL,
            year INTEGER NOT NULL,
            UNIQUE(tenant_id, week, year)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS menu_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            meal TEXT NOT NULL,
            variant_type TEXT NOT NULL,
            dish_id INTEGER,
            UNIQUE(menu_id, day, meal, variant_type)
        )
    """))
    
    # Clear existing data
    conn.execute(text("DELETE FROM menu_variants"))
    conn.execute(text("DELETE FROM menus"))
    conn.execute(text("DELETE FROM dishes"))
    
    # Seed menu for week 48/2025
    conn.execute(
        text("INSERT INTO menus (tenant_id, week, year, status) VALUES (:tid, :week, :year, :status)"),
        {"tid": 1, "week": 48, "year": 2025, "status": "draft"}
    )
    menu_id = conn.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
    
    # Seed dishes
    conn.execute(text("INSERT INTO dishes (tenant_id, name, category) VALUES (:tid, :name, :cat)"), {"tid": 1, "name": "Köttbullar", "cat": None})
    dish1_id = conn.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
    
    conn.execute(text("INSERT INTO dishes (tenant_id, name, category) VALUES (:tid, :name, :cat)"), {"tid": 1, "name": "Fiskgratäng", "cat": None})
    dish2_id = conn.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
    
    conn.execute(text("INSERT INTO dishes (tenant_id, name, category) VALUES (:tid, :name, :cat)"), {"tid": 1, "name": "Glass", "cat": None})
    dish3_id = conn.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
    
    # Seed menu variants for Monday lunch
    conn.execute(
        text("INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id) VALUES (:mid, :day, :meal, :vt, :did)"),
        {"mid": menu_id, "day": "Mon", "meal": "Lunch", "vt": "alt1", "did": dish1_id}
    )
    conn.execute(
        text("INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id) VALUES (:mid, :day, :meal, :vt, :did)"),
        {"mid": menu_id, "day": "Mon", "meal": "Lunch", "vt": "alt2", "did": dish2_id}
    )
    conn.execute(
        text("INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id) VALUES (:mid, :day, :meal, :vt, :did)"),
        {"mid": menu_id, "day": "Mon", "meal": "Lunch", "vt": "dessert", "did": dish3_id}
    )
    
    conn.commit()
    yield app_session
    
    # Cleanup
    conn.execute(text("DELETE FROM menu_variants"))
    conn.execute(text("DELETE FROM menus"))
    conn.execute(text("DELETE FROM dishes"))
    conn.commit()


@pytest.fixture
def client_admin(app_with_menu: Flask) -> FlaskClient:
    """Authenticated test client for admin routes."""
    return app_with_menu.test_client()


def test_admin_menu_import_list_shows_weeks(client_admin: FlaskClient):
    """List route displays weeks with menu data."""
    response = client_admin.get("/ui/admin/menu-import", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check page structure
    assert "Menyimport" in html
    assert "Ladda upp menyfil" in html
    
    # Check seeded week appears in list
    assert "2025" in html
    assert "48" in html
    assert "Visa / Redigera" in html


def test_admin_menu_import_upload_shows_flash(client_admin: FlaskClient):
    """Upload route shows flash message for received file."""
    # Create fake file upload
    data = {
        "menu_file": (BytesIO(b"fake menu content"), "test_menu.pdf")
    }
    
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type="multipart/form-data",
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check flash message appears
    assert "mottagen" in html.lower()
    assert "implementeras senare" in html.lower() or "test_menu.pdf" in html


def test_admin_menu_import_upload_no_file_shows_error(client_admin: FlaskClient):
    """Upload without file shows error message."""
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data={},
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check error flash message
    assert "ingen fil" in html.lower() or "error" in html.lower()


def test_admin_menu_import_week_shows_menu_data(client_admin: FlaskClient):
    """Week detail route displays menu variants for seeded week."""
    response = client_admin.get("/ui/admin/menu-import/week/2025/48", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check page structure
    assert "vecka 48" in html.lower()
    assert "2025" in html
    
    # Check menu data appears
    assert "Mon" in html
    assert "Lunch" in html
    assert "Köttbullar" in html
    assert "Fiskgratäng" in html
    assert "Glass" in html


def test_admin_menu_import_week_nonexistent_shows_warning(client_admin: FlaskClient):
    """Week detail for non-existent menu shows warning and redirects."""
    response = client_admin.get("/ui/admin/menu-import/week/2099/99", headers=ADMIN_HEADERS, follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode()
    
    # Should redirect back to list with flash message
    assert "ingen meny" in html.lower() or "hittades inte" in html.lower()
    assert "Menyimport" in html  # back on list page


def test_admin_menu_import_list_empty_when_no_menus(app_session: Flask):
    """List shows appropriate message when no menus exist."""
    from core.db import get_session
    from sqlalchemy import text
    
    conn = get_session()
    conn.execute(text("DELETE FROM menu_variants"))
    conn.execute(text("DELETE FROM menus"))
    conn.commit()
    
    client = app_session.test_client()
    response = client.get("/ui/admin/menu-import", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check empty state
    assert "Menyimport" in html
    assert "inga importerade menyer" in html.lower() or "ännu" in html.lower()
