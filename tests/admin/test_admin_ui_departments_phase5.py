"""Test Admin Phase 5: Avdelningseditor (departments list + edit).

Verifies:
- /ui/admin/departments lists all departments with site names
- /ui/admin/departments/<id>/edit GET shows form
- /ui/admin/departments/<id>/edit POST updates department and redirects
"""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

# Auth headers for admin routes
ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def app_with_departments(app_session: Flask) -> Flask:
    """Seed one site and one department for testing."""
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        # Ensure tables exist (sqlite dev)
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS sites (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS departments (
              id TEXT PRIMARY KEY,
              site_id TEXT NOT NULL,
              name TEXT NOT NULL,
              resident_count_mode TEXT NOT NULL DEFAULT 'fixed',
              resident_count_fixed INTEGER NOT NULL DEFAULT 0,
              notes TEXT NULL,
              version INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT
            )
        """))
        # Insert test site
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-test-1', 'Test Site')"))
        # Insert test department
        db.execute(text("""
            INSERT OR IGNORE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version)
            VALUES ('dept-test-1', 'site-test-1', 'Test Avdelning', 'fixed', 10, 'Test faktaruta', 0)
        """))
        db.commit()
    finally:
        db.close()
    return app_session


def test_admin_departments_list_shows_departments(app_with_departments: Flask, client_admin: FlaskClient) -> None:
    """GET /ui/admin/departments should list all departments with site names."""
    resp = client_admin.get("/ui/admin/departments", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Avdelningar" in html
    assert "Test Avdelning" in html
    assert "Test Site" in html
    assert "Redigera" in html


def test_admin_department_edit_get_shows_form(app_with_departments: Flask, client_admin: FlaskClient) -> None:
    """GET /ui/admin/departments/<id>/edit should show edit form with current values."""
    resp = client_admin.get("/ui/admin/departments/dept-test-1/edit", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Redigera Avdelning" in html
    assert 'value="Test Avdelning"' in html
    assert 'value="10"' in html
    assert "Test faktaruta" in html


def test_admin_department_edit_post_updates_department(app_with_departments: Flask, client_admin: FlaskClient) -> None:
    """POST /ui/admin/departments/<id>/edit should update department and redirect to list."""
    resp = client_admin.post(
        "/ui/admin/departments/dept-test-1/edit",
        data={
            "name": "Updated Avdelning",
            "resident_count_fixed": "15",
            "notes": "Updated faktaruta",
        },
        headers=ADMIN_HEADERS,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    # Should redirect to list and show updated name
    assert "Avdelningar" in html
    assert "Updated Avdelning" in html
    assert "uppdaterad" in html.lower()  # flash message


def test_admin_departments_list_empty_when_no_departments(app_session: Flask, client_admin: FlaskClient) -> None:
    """GET /ui/admin/departments should show empty state when no departments exist."""
    resp = client_admin.get("/ui/admin/departments", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Inga avdelningar hittades" in html or "Inga avdelningar" in html
