"""
Tests for Unified Admin Panel - User Management (Phase 3)

Tests cover:
- Permissions (admin/superuser OK, staff/cook denied)
- List view
- Create user
- Edit user
- Deactivate user
- Reset password stub
- Regression checks
"""

import uuid
import pytest
from sqlalchemy import text

from core.db import get_session


def _h(role):
    """Helper to create auth headers for tests."""
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


# ============================================================================
# PERMISSIONS TESTS
# ============================================================================

def test_users_list_permissions_admin_allowed(client_admin):
    """Test admin can view users list"""
    resp = client_admin.get("/ui/admin/users", headers=_h("admin"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Användare" in html


def test_users_list_permissions_superuser_allowed(client_superuser):
    """Test superuser can view users list"""
    resp = client_superuser.get("/ui/admin/users", headers=_h("superuser"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Användare" in html


def test_users_list_permissions_staff_denied(client_user):
    """Test staff cannot view users list"""
    resp = client_user.get("/ui/admin/users", headers=_h("staff"))
    
    assert resp.status_code == 403


def test_users_new_form_permissions_staff_denied(client_user):
    """Test staff cannot access new user form"""
    resp = client_user.get("/ui/admin/users/new", headers=_h("staff"))
    
    assert resp.status_code == 403


# ============================================================================
# LIST VIEW TESTS
# ============================================================================

def test_users_list_shows_users(client_admin):
    """Test users list displays all tenant users"""
    app = client_admin.application
    
    # Create test users
    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            
            # Create two users (use auto-increment IDs)
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'admin_test@test.com', :ph, 'admin', 'admin_user_test', 'Admin User Test', 1)"
                ),
                {"ph": pw_hash}
            )
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'staff_test@test.com', :ph, 'staff', 'staff_user_test', 'Staff User Test', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.get("/ui/admin/users", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "admin_user_test" in html
    assert "staff_user_test" in html


def test_users_list_shows_roles(client_admin):
    """Test users list displays user roles"""
    app = client_admin.application
    
    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'admin_role_test@test.com', :ph, 'admin', 'admin_role_user', 'Admin Role User', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.get("/ui/admin/users", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Admin" in html  # Role badge


def test_users_list_shows_active_status(client_admin):
    """Test users list shows active/inactive status"""
    app = client_admin.application
    
    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            # Active user
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'active_status_test@test.com', :ph, 'staff', 'active_status_user', 'Active Status User', 1)"
                ),
                {"ph": pw_hash}
            )
            # Inactive user
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'inactive_status_test@test.com', :ph, 'staff', 'inactive_status_user', 'Inactive Status User', 0)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.get("/ui/admin/users", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Aktiv" in html
    assert "Inaktiv" in html


# ============================================================================
# CREATE USER TESTS
# ============================================================================

def test_users_new_form_renders(client_admin):
    """Test new user form renders correctly"""
    resp = client_admin.get("/ui/admin/users/new", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Ny användare" in html
    assert "Användarnamn" in html
    assert "E-post" in html
    assert "Lösenord" in html
    assert "Roll" in html


def test_users_create_success(client_admin):
    """Test creating a new user"""
    app = client_admin.application
    
    resp = client_admin.post("/ui/admin/users/new", data={
        "username": "newuser_create_test",
        "email": "newuser_create@test.com",
        "full_name": "New User Create",
        "password": "password123",
        "role": "staff"
    }, headers=_h("admin"), follow_redirects=True)
    
    html = resp.data.decode("utf-8")
    assert resp.status_code == 200
    
    # Verify user was created in database
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT username, email, role, is_active FROM users WHERE username = 'newuser_create_test'")
            ).fetchone()
            assert row is not None
            assert row[0] == "newuser_create_test"
            assert row[1] == "newuser_create@test.com"
            assert row[2] == "staff"
            assert row[3] == 1  # is_active
        finally:
            db.close()


def test_users_create_validates_required_fields(client_admin):
    """Test user creation requires username, email, password"""
    # Missing username
    resp = client_admin.post("/ui/admin/users/new", data={
        "email": "test_validation@test.com",
        "password": "pass123",
        "role": "staff"
    }, headers=_h("admin"), follow_redirects=True)
    html = resp.data.decode("utf-8")
    assert "måste anges" in html.lower()


def test_users_create_prevents_duplicate_username(client_admin):
    """Test cannot create user with duplicate username"""
    app = client_admin.application
    
    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'existing_dup_username@test.com', :ph, 'admin', 'existing_user_dup', 'Existing User Dup', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.post("/ui/admin/users/new", data={
        "username": "existing_user_dup",  # Already exists
        "email": "different_dup@test.com",
        "password": "pass123",
        "role": "staff"
    }, headers=_h("admin"), follow_redirects=True)
    
    html = resp.data.decode("utf-8")
    assert "finns redan" in html.lower()


def test_users_create_prevents_duplicate_email(client_admin):
    """Test cannot create user with duplicate email"""
    app = client_admin.application
    
    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'existing_dup_email@test.com', :ph, 'admin', 'existing_email_user', 'Existing Email User', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.post("/ui/admin/users/new", data={
        "username": "newuser_dup_email",
        "email": "existing_dup_email@test.com",  # Already exists
        "password": "pass123",
        "role": "staff"
    }, headers=_h("admin"), follow_redirects=True)
    
    html = resp.data.decode("utf-8")
    assert "används redan" in html.lower() or "finns redan" in html.lower()


# ============================================================================
# EDIT USER TESTS
# ============================================================================

def test_users_edit_form_renders(client_admin):
    """Test edit user form renders with existing data"""
    app = client_admin.application
    
    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'edit_form_test@test.com', :ph, 'staff', 'edit_form_user', 'Edit Form User', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
            # Get the auto-generated ID
            user_id = db.execute(text("SELECT id FROM users WHERE username = 'edit_form_user'")).fetchone()[0]
        finally:
            db.close()
    
    resp = client_admin.get(f"/ui/admin/users/{user_id}/edit", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Redigera användare" in html
    assert "edit_form_user" in html
    assert "edit_form_test@test.com" in html


def test_users_update_success(client_admin):
    """Test updating a user"""
    app = client_admin.application
    
    with app.app_context():
        from core.db import create_all
        create_all()
        
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (id, tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 1, 'update@test.com', :ph, 'staff', 'update_user', 'Update Me', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.post("/ui/admin/users/1/edit", data={
        "email": "updated@test.com",
        "full_name": "Updated Name",
        "role": "cook"
    }, headers=_h("admin"), follow_redirects=True)
    
    assert resp.status_code == 200
    
    # Verify changes
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT email, full_name, role FROM users WHERE id = 1")
            ).fetchone()
            assert row[0] == "updated@test.com"
            assert row[1] == "Updated Name"
            assert row[2] == "cook"
        finally:
            db.close()


# ============================================================================
# DEACTIVATE USER TESTS
# ============================================================================

def test_users_deactivate_success(client_admin):
    """Test deactivating a user"""
    app = client_admin.application
    
    with app.app_context():
        from core.db import create_all
        create_all()
        
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (id, tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (2, 1, 'deactivate@test.com', :ph, 'staff', 'deactivate_user', 'Deactivate Me', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.post("/ui/admin/users/2/deactivate", headers=_h("admin"), follow_redirects=True)
    
    assert resp.status_code == 200
    
    # Verify user is inactive
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT is_active FROM users WHERE id = 2")
            ).fetchone()
            assert row[0] == 0  # is_active = False
        finally:
            db.close()


def test_users_deactivate_prevents_self(client_admin):
    """Test cannot deactivate your own account"""
    app = client_admin.application
    
    with app.app_context():
        from core.db import create_all
        create_all()
    
    resp = client_admin.post("/ui/admin/users/1/deactivate", headers=_h("admin"), follow_redirects=True)
    html = resp.data.decode("utf-8")
    
    assert "eget konto" in html.lower() or "kan inte" in html.lower()


# ============================================================================
# RESET PASSWORD TESTS
# ============================================================================

def test_users_reset_password_stub(client_admin):
    """Test password reset generates temporary password"""
    app = client_admin.application
    
    with app.app_context():
        from core.db import create_all
        create_all()
        
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash("oldpass")
            db.execute(
                text(
                    "INSERT INTO users (id, tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (2, 1, 'reset@test.com', :ph, 'staff', 'reset_user', 'Reset User', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.post("/ui/admin/users/2/reset-password", headers=_h("admin"), follow_redirects=True)
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Tillfälligt lösenord" in html or "lösenord" in html.lower()


# ============================================================================
# REGRESSION TESTS
# ============================================================================

def test_admin_dashboard_still_works(client_admin):
    """Test Phase 1 admin dashboard still works"""
    resp = client_admin.get("/ui/admin", headers=_h("admin"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Admin" in html


def test_departments_still_work(client_admin):
    """Test Phase 2 departments still work"""
    app = client_admin.application
    
    with app.app_context():
        from core.db import create_all
        create_all()
        
        site_id = str(uuid.uuid4())
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            db.commit()
        finally:
            db.close()
    
    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Avdelningar" in html
