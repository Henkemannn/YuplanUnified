"""Admin UI menu import Phase 8 tests - Full CSV import functionality."""
from __future__ import annotations

import io
import pytest
from sqlalchemy import text


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


# Sample CSV content for testing
SAMPLE_CSV = """Year,Week,Weekday,Meal,Alt,Text
2025,49,Måndag,Lunch,Alt1,Köttbullar med potatis
2025,49,Måndag,Lunch,Alt2,Fiskgratäng
2025,49,Måndag,Lunch,Dessert,Glass med bär
2025,49,Måndag,Kvällsmat,,Smörgåsar
2025,49,Tisdag,Lunch,Alt1,Pasta carbonara
2025,49,Tisdag,Lunch,Alt2,Vegetarisk lasagne
2025,49,Tisdag,Lunch,Dessert,Frukt
2025,49,Tisdag,Kvällsmat,,Mackor
2025,50,Måndag,Lunch,Alt1,Pannkakor med sylt
2025,50,Måndag,Lunch,Alt2,Omelett
2025,50,Måndag,Lunch,Dessert,Yoghurt
2025,50,Måndag,Kvällsmat,,Bröd och pålägg
"""


@pytest.fixture
def csv_file_content():
    """Return sample CSV content as bytes."""
    return SAMPLE_CSV.encode('utf-8')


def test_upload_csv_creates_menus(app_session, client_admin, csv_file_content):
    """Test uploading a CSV file creates menu entries in database."""
    from core.db import get_session
    
    # Clean menus table first
    db = get_session()
    try:
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.commit()
    finally:
        db.close()
    
    # Upload CSV
    data = {
        'menu_file': (io.BytesIO(csv_file_content), 'test_menu.csv')
    }
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type='multipart/form-data',
        headers=ADMIN_HEADERS
    )
    
    # Should redirect to menu import page
    assert response.status_code == 302
    assert "/ui/admin/menu-import" in response.location
    
    # Verify menus created in database
    db = get_session()
    try:
        rows = db.execute(
            text("SELECT DISTINCT year, week FROM menus WHERE tenant_id = :tid ORDER BY year, week"),
            {"tid": 1}
        ).fetchall()
        
        # Should have week 49 and 50 from 2025
        assert len(rows) == 2
        assert rows[0] == (2025, 49)
        assert rows[1] == (2025, 50)
    finally:
        db.close()


def test_week_list_shows_imported_weeks(app_session, client_admin, csv_file_content):
    """Test that week list page shows weeks from imported CSV."""
    from core.db import get_session
    
    # Clean and upload
    db = get_session()
    try:
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.commit()
    finally:
        db.close()
    
    data = {'menu_file': (io.BytesIO(csv_file_content), 'test.csv')}
    client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type='multipart/form-data',
        headers=ADMIN_HEADERS
    )
    
    # Get week list
    response = client_admin.get("/ui/admin/menu-import", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Should show both weeks
    assert "2025" in html
    assert "49" in html
    assert "50" in html


def test_week_detail_shows_imported_dishes(app_session, client_admin, csv_file_content):
    """Test week detail page displays dishes from imported CSV."""
    from core.db import get_session
    
    # Clean and upload
    db = get_session()
    try:
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.commit()
    finally:
        db.close()
    
    data = {'menu_file': (io.BytesIO(csv_file_content), 'test.csv')}
    client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type='multipart/form-data',
        headers=ADMIN_HEADERS
    )
    
    # Get week 49 detail
    response = client_admin.get("/ui/admin/menu-import/week/2025/49", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Should show dishes from CSV
    assert "Köttbullar med potatis" in html or "köttbullar" in html.lower()
    assert "Fiskgratäng" in html or "fiskgratäng" in html.lower()
    assert "Glass med bär" in html or "glass" in html.lower()
    assert "Smörgåsar" in html or "smörgås" in html.lower()


def test_upload_invalid_csv_shows_error(app_session, client_admin):
    """Test uploading invalid CSV shows 'Ogiltigt menyformat' error."""
    invalid_csv = b"invalid,csv\nno,proper,headers"
    
    data = {
        'menu_file': (io.BytesIO(invalid_csv), 'bad.csv')
    }
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type='multipart/form-data',
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Ogiltigt menyformat" in html


def test_upload_non_csv_file_rejects(app_session, client_admin):
    """Test uploading non-CSV file is rejected."""
    data = {
        'menu_file': (io.BytesIO(b"some content"), 'test.txt')
    }
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type='multipart/form-data',
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Ogiltigt menyformat" in html


def test_upload_no_file_shows_error(app_session, client_admin):
    """Test uploading without file shows error."""
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data={},
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Ingen fil vald" in html


def test_upload_success_shows_summary(app_session, client_admin, csv_file_content):
    """Test successful upload shows import summary."""
    from core.db import get_session
    
    # Clean first
    db = get_session()
    try:
        db.execute(text("DELETE FROM menu_variants"))
        db.execute(text("DELETE FROM menus"))
        db.commit()
    finally:
        db.close()
    
    data = {'menu_file': (io.BytesIO(csv_file_content), 'test.csv')}
    response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type='multipart/form-data',
        headers=ADMIN_HEADERS,
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Should show success message with summary
    assert "importerad" in html.lower() or "skapade" in html.lower()
