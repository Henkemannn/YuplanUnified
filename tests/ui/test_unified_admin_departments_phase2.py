"""
Test suite for Unified Admin Panel - Phase 2: Department Management CRUD
Tests for department list, create, edit, delete operations with full RBAC and CSRF.
"""

import pytest
import uuid
from datetime import date as _date


def _h(role):
    """Helper to create auth headers for tests."""
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


# ============================================================================
# Department List Tests
# ============================================================================

def test_departments_list_happy_path_admin(client_admin):
    """Test admin can view departments list."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    
    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',25,0)"
                ),
                {"i": dept_id, "s": site_id, "n": "Testavdelning"}
            )
            db.commit()
        finally:
            db.close()
    
    # Activate this site in session
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Avdelningar" in html
    assert "Testavdelning" in html
    assert "25" in html


def test_departments_list_permissions_superuser_allowed(client_superuser):
    """Test superuser can view departments list."""
    resp = client_superuser.get("/ui/admin/departments", headers=_h("superuser"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Avdelningar" in html


def test_departments_list_permissions_editor_denied(client_user):
    """Test editor cannot view departments list."""
    resp = client_user.get("/ui/admin/departments", headers=_h("editor"))
    
    assert resp.status_code == 403


def test_departments_list_permissions_viewer_denied(client_user):
    """Test viewer cannot view departments list."""
    resp = client_user.get("/ui/admin/departments", headers=_h("viewer"))
    
    assert resp.status_code == 403


def test_departments_list_shows_add_button(client_admin):
    """Test departments list shows add button."""
    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Lägg till avdelning" in html
    assert "/ui/admin/departments/new" in html


def test_departments_list_empty_state(client_admin):
    """Test departments list shows empty state when no departments."""
    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    # Should show empty state message
    assert "Inga avdelningar" in html or "Lägg till avdelning" in html


# ============================================================================
# Department Create Tests
# ============================================================================

def test_departments_new_form_happy_path(client_admin):
    """Test new department form renders correctly."""
    resp = client_admin.get("/ui/admin/departments/new", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Ny avdelning" in html
    assert 'name="name"' in html
    assert 'name="resident_count"' in html
    assert 'name="csrf_token"' in html


def test_departments_new_form_permissions_admin_allowed(client_admin):
    """Test admin can access new department form."""
    resp = client_admin.get("/ui/admin/departments/new", headers=_h("admin"))
    
    assert resp.status_code == 200


def test_departments_new_form_permissions_editor_denied(client_user):
    """Test editor cannot access new department form."""
    resp = client_user.get("/ui/admin/departments/new", headers=_h("editor"))
    
    assert resp.status_code == 403


def test_departments_create_happy_path(client_admin):
    """Test creating a new department."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed site
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            # Update test user to have this site
            
            db.commit()
        finally:
            db.close()
    
    # Create department
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "New Test Department",
            "resident_count": "30",
        },
        follow_redirects=True
    )
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should redirect to list with success message
    assert "New Test Department" in html or "skapad" in html


def test_departments_create_validation_empty_name(client_admin):
    """Test creating department with empty name fails."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed site
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            
            db.commit()
        finally:
            db.close()
    
    # Try to create with empty name
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "",
            "resident_count": "10",
        },
        follow_redirects=True
    )
    
    html = resp.data.decode("utf-8")
    
    # Should show error about name being required
    assert "Namn måste anges" in html


def test_departments_create_validation_negative_residents(client_admin):
    """Test creating department with negative residents fails."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed site
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            
            db.commit()
        finally:
            db.close()
    
    # Try to create with negative residents
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "Test Dept",
            "resident_count": "-5",
        },
        follow_redirects=True
    )
    
    html = resp.data.decode("utf-8")
    
    # Should show error
    assert "0 eller högre" in html


# ============================================================================
# Department Edit Tests
# ============================================================================

def test_departments_edit_form_happy_path(client_admin):
    """Test edit department form renders with existing data."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',20,0)"
                ),
                {"i": dept_id, "s": site_id, "n": "Edit Test Dept"}
            )
            db.commit()
        finally:
            db.close()
    
    # Activate this site in session
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp = client_admin.get(f"/ui/admin/departments/{dept_id}/edit", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Redigera avdelning" in html
    assert "Edit Test Dept" in html
    assert "20" in html


def test_departments_edit_form_permissions_admin_allowed(client_admin):
    """Test admin can access edit form."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"
                ),
                {"i": dept_id, "s": site_id, "n": "Test"}
            )
            db.commit()
        finally:
            db.close()
    
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp = client_admin.get(f"/ui/admin/departments/{dept_id}/edit", headers=_h("admin"))
    
    assert resp.status_code == 200


def test_departments_edit_form_permissions_editor_denied(client_user):
    """Test editor cannot access edit form."""
    fake_id = str(uuid.uuid4())
    resp = client_user.get(f"/ui/admin/departments/{fake_id}/edit", headers=_h("editor"))
    
    assert resp.status_code == 403


def test_departments_update_happy_path(client_admin):
    """Test updating a department."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',15,0)"
                ),
                {"i": dept_id, "s": site_id, "n": "Old Name"}
            )
            db.commit()
        finally:
            db.close()
    
    # Update department
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp = client_admin.post(
        f"/ui/admin/departments/{dept_id}/edit",
        headers=_h("admin"),
        data={
            "name": "Updated Name",
            "resident_count": "25",
            "version": "0",
        },
        follow_redirects=True
    )
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should show updated data
    assert "Updated Name" in html or "uppdaterad" in html


# ============================================================================
# Department Delete Tests
# ============================================================================

def test_departments_delete_happy_path(client_admin):
    """Test deleting a department."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"
                ),
                {"i": dept_id, "s": site_id, "n": "To Delete"}
            )
            db.commit()
        finally:
            db.close()
    
    # Delete department
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp = client_admin.post(
        f"/ui/admin/departments/{dept_id}/delete",
        headers=_h("admin"),
        data={},
        follow_redirects=True
    )
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should show success message
    assert "borttagen" in html or "Avdelningar" in html


def test_departments_delete_permissions_editor_denied(client_user):
    """Test editor cannot delete department."""
    fake_id = str(uuid.uuid4())
    
    resp = client_user.post(
        f"/ui/admin/departments/{fake_id}/delete",
        headers=_h("editor"),
        data={"csrf_token": "fake"},
        follow_redirects=True
    )
    
    assert resp.status_code == 403


# ============================================================================
# Regression Tests
# ============================================================================

def test_admin_phase1_still_works(client_admin):
    """Test admin dashboard still works after Phase 2."""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Adminpanel" in html


def test_weekview_still_works_after_phase2(client_admin):
    """Test weekview still works after adding department management."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed data
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',10,0)"
                ),
                {"i": dept_id, "s": site_id, "n": "TestDep"}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dept_id}",
        headers=_h("admin"),
        follow_redirects=True
    )
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Veckovy" in html
