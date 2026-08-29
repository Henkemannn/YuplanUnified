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

import re
import uuid
import pytest
from sqlalchemy import text

from core.db import get_session


def _h(role):
    """Helper to create auth headers for tests."""
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def _csrf_from_html(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None, "CSRF token missing from rendered HTML"
    return match.group(1)


def _form_csrf(client_admin, path: str) -> str:
    resp = client_admin.get(path, headers=_h("admin"))
    assert resp.status_code == 200
    return _csrf_from_html(resp.data.decode("utf-8"))


def _list_csrf(client_admin) -> str:
    resp = client_admin.get("/ui/admin/users", headers=_h("admin"))
    assert resp.status_code == 200
    return _csrf_from_html(resp.data.decode("utf-8"))


def _seed_unit_portal_department(app, *, tenant_id: int, site_id: str, department_id: str, site_name: str = "Site") -> None:
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:tid, :name, 1)"), {"tid": tenant_id, "name": f"Tenant {tenant_id}"})
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, :tid, 0)"),
                {"sid": site_id, "name": site_name, "tid": tenant_id},
            )
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:did, :sid, :name, 'manual')"),
                {"did": department_id, "sid": site_id, "name": f"Dept {department_id[:8]}"},
            )
            db.commit()
        finally:
            db.close()


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
    assert 'name="csrf_token"' in html


def test_users_create_success(client_admin):
    """Test creating a new user"""
    app = client_admin.application
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    
    resp = client_admin.post("/ui/admin/users/new", data={
        "username": "newuser_create_test",
        "email": "NewUser_Create@Test.com",
        "full_name": "New User Create",
        "password": "password123",
        "role": "staff",
        "csrf_token": csrf_token,
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
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post("/ui/admin/users/new", data={
        "email": "test_validation@test.com",
        "password": "pass123",
        "role": "staff",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)
    html = resp.data.decode("utf-8")
    assert "måste anges" in html.lower()


def test_users_create_invalid_csrf_rejected(client_admin):
    """Test invalid CSRF blocks user creation."""
    app = client_admin.application
    prev_strict = app.config.get("STRICT_CSRF_IN_TESTS")
    app.config["STRICT_CSRF_IN_TESTS"] = True
    resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "username": "badcsrf_user",
            "email": "badcsrf@test.com",
            "full_name": "Bad CSRF",
            "password": "password123",
            "role": "staff",
            "csrf_token": "bogus",
        },
        headers=_h("admin"),
        follow_redirects=False,
    )
    app.config["STRICT_CSRF_IN_TESTS"] = prev_strict
    assert resp.status_code == 403
    body = resp.get_json(silent=True) or {}
    assert body.get("detail") == "invalid_csrf" or "invalid_csrf" in resp.get_data(as_text=True)


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
    
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post("/ui/admin/users/new", data={
        "username": "existing_user_dup",  # Already exists
        "email": "different_dup@test.com",
        "password": "pass123",
        "role": "staff",
        "csrf_token": csrf_token,
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
    
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post("/ui/admin/users/new", data={
        "username": "newuser_dup_email",
        "email": "Existing_Dup_Email@Test.com",  # Already exists
        "password": "pass123",
        "role": "staff",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)
    
    html = resp.data.decode("utf-8")
    assert "används redan" in html.lower() or "finns redan" in html.lower()


def test_users_update_rejects_case_insensitive_duplicate_email(client_admin):
    """Test updating a user rejects duplicate email ignoring case."""
    app = client_admin.application

    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash

            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'existing@example.com', :ph, 'staff', 'existing_user_case', 'Existing User Case', 1)"
                ),
                {"ph": pw_hash},
            )
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'other@example.com', :ph, 'staff', 'other_user_case', 'Other User Case', 1)"
                ),
                {"ph": pw_hash},
            )
            db.commit()
            user_b_id = db.execute(text("SELECT id FROM users WHERE username = 'other_user_case' LIMIT 1")).fetchone()[0]
        finally:
            db.close()

    csrf_token = _form_csrf(client_admin, f"/ui/admin/users/{user_b_id}/edit")
    resp = client_admin.post(
        f"/ui/admin/users/{user_b_id}/edit",
        data={
            "email": "Existing@Example.COM",
            "full_name": "Other User Case",
            "role": "staff",
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    html = resp.data.decode("utf-8")
    assert resp.status_code == 200
    assert "används redan" in html.lower() or "finns redan" in html.lower()

    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT email FROM users WHERE id = :uid"),
                {"uid": user_b_id},
            ).fetchone()
            assert row is not None
            assert row[0] == "other@example.com"
        finally:
            db.close()


def test_users_create_unit_portal_requires_tenant_department(client_admin):
    """Test unit_portal users must be bound to a department in the current tenant."""
    app = client_admin.application
    dept_id = str(uuid.uuid4())
    site_id = str(uuid.uuid4())
    _seed_unit_portal_department(app, tenant_id=1, site_id=site_id, department_id=dept_id)

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "username": "portal_user_ok",
            "email": "portal_user_ok@test.com",
            "full_name": "Portal User OK",
            "password": "password123",
            "role": "unit_portal",
            "department_id": dept_id,
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    assert resp.status_code == 200
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT role, department_id FROM users WHERE username = 'portal_user_ok'"),
            ).fetchone()
            assert row is not None
            assert row[0] == "unit_portal"
            assert row[1] == dept_id
        finally:
            db.close()


def test_users_create_unit_portal_rejects_cross_tenant_department(client_admin):
    """Test unit_portal create rejects departments from another tenant."""
    app = client_admin.application
    dept_id = str(uuid.uuid4())
    site_id = str(uuid.uuid4())
    _seed_unit_portal_department(app, tenant_id=2, site_id=site_id, department_id=dept_id, site_name="Other Site")

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "username": "portal_user_bad",
            "email": "portal_user_bad@test.com",
            "full_name": "Portal User Bad",
            "password": "password123",
            "role": "unit_portal",
            "department_id": dept_id,
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "tillhör inte din tenant" in html.lower()


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
    assert 'name="csrf_token"' in html


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
                    "INSERT OR IGNORE INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'update@test.com', :ph, 'staff', 'update_user', 'Update Me', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
            user_id = db.execute(
                text("SELECT id FROM users WHERE email='update@test.com' LIMIT 1")
            ).fetchone()[0]
        finally:
            db.close()
    csrf_token = _form_csrf(client_admin, f"/ui/admin/users/{user_id}/edit")

    resp = client_admin.post(f"/ui/admin/users/{user_id}/edit", data={
        "email": "Portal_Edit_Updated2@Test.com",
        "full_name": "Updated Name",
        "role": "cook",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)

    assert resp.status_code == 200

    # Verify changes
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT email, full_name, role FROM users WHERE id = :uid"),
                {"uid": user_id}
            ).fetchone()
            assert row[0] == "portal_edit_updated2@test.com"
            assert row[1] == "Updated Name"
            assert row[2] == "cook"
        finally:
            db.close()


def test_users_update_unit_portal_rejects_cross_tenant_department(client_admin):
    """Test editing a unit_portal user cannot move them to another tenant's department."""
    app = client_admin.application
    dept_a = str(uuid.uuid4())
    site_a = str(uuid.uuid4())
    dept_b = str(uuid.uuid4())
    site_b = str(uuid.uuid4())
    _seed_unit_portal_department(app, tenant_id=1, site_id=site_a, department_id=dept_a, site_name="Tenant One Site")
    _seed_unit_portal_department(app, tenant_id=2, site_id=site_b, department_id=dept_b, site_name="Tenant Two Site")

    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash

            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active, department_id) "
                    "VALUES (1, 'portal_edit@test.com', :ph, 'unit_portal', 'portal_edit_user', 'Portal Edit User', 1, :dept)"
                ),
                {"ph": pw_hash, "dept": dept_a},
            )
            db.commit()
            user_id = db.execute(text("SELECT id FROM users WHERE username = 'portal_edit_user' LIMIT 1")).fetchone()[0]
        finally:
            db.close()

    csrf_token = _form_csrf(client_admin, f"/ui/admin/users/{user_id}/edit")
    resp = client_admin.post(
        f"/ui/admin/users/{user_id}/edit",
        data={
            "email": "portal_edit_updated@test.com",
            "full_name": "Portal Edit Updated",
            "role": "unit_portal",
            "department_id": dept_b,
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "tillhör inte din tenant" in html.lower()
    
    csrf_token = _form_csrf(client_admin, f"/ui/admin/users/{user_id}/edit")
    resp = client_admin.post(f"/ui/admin/users/{user_id}/edit", data={
        "email": "updated@test.com",
        "full_name": "Updated Name",
        "role": "cook",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)
    
    assert resp.status_code == 200
    
    # Verify changes
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT email, full_name, role FROM users WHERE id = :uid"),
                {"uid": user_id}
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
                    "INSERT OR IGNORE INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'deactivate@test.com', :ph, 'staff', 'deactivate_user', 'Deactivate Me', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
            user_id = db.execute(
                text("SELECT id FROM users WHERE email='deactivate@test.com' LIMIT 1")
            ).fetchone()[0]
        finally:
            db.close()
    
    csrf_token = _list_csrf(client_admin)
    resp = client_admin.post(f"/ui/admin/users/{user_id}/deactivate", data={"csrf_token": csrf_token}, headers=_h("admin"), follow_redirects=True)
    
    assert resp.status_code == 200
    
    # Verify user is inactive
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT is_active FROM users WHERE id = :uid"),
                {"uid": user_id}
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
    
    csrf_token = _list_csrf(client_admin)
    resp = client_admin.post("/ui/admin/users/1/deactivate", data={"csrf_token": csrf_token}, headers=_h("admin"), follow_redirects=True)
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
                    "INSERT OR IGNORE INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, 'reset@test.com', :ph, 'staff', 'reset_user', 'Reset User', 1)"
                ),
                {"ph": pw_hash}
            )
            db.commit()
            user_id = db.execute(
                text("SELECT id FROM users WHERE email='reset@test.com' LIMIT 1")
            ).fetchone()[0]
        finally:
            db.close()
    
    csrf_token = _list_csrf(client_admin)
    resp = client_admin.post(f"/ui/admin/users/{user_id}/reset-password", data={"csrf_token": csrf_token}, headers=_h("admin"), follow_redirects=True)
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
