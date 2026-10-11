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

from core.admin_repo import ResidencesRepo
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


def _seed_unit_portal_department(
    app,
    *,
    tenant_id: int,
    site_id: str,
    department_id: str,
    site_name: str = "Site",
    department_name: str | None = None,
    residence_name: str | None = None,
) -> None:
    with app.app_context():
        residence_id = ResidencesRepo().create_for_site(site_id, residence_name)["id"] if residence_name else None
        db = get_session()
        try:
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:tid, :name, 1)"), {"tid": tenant_id, "name": f"Tenant {tenant_id}"})
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, :tid, 0)"),
                {"sid": site_id, "name": site_name, "tid": tenant_id},
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO departments(id, site_id, name, residence_id, resident_count_mode) "
                    "VALUES(:did, :sid, :name, :rid, 'manual')"
                ),
                {
                    "did": department_id,
                    "sid": site_id,
                    "name": department_name or f"Dept {department_id[:8]}",
                    "rid": residence_id,
                },
            )
            db.commit()
        finally:
            db.close()


def _seed_department_scope_matrix(app, *, active_site_id: str, other_site_id: str, foreign_site_id: str) -> dict[str, str]:
    active_dept = str(uuid.uuid4())
    other_dept = str(uuid.uuid4())
    foreign_tenant_id = 2
    foreign_dept = str(uuid.uuid4())
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(1, 'Tenant 1', 1)"))
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(2, 'Tenant 2', 1)"))
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, 1, 0)"),
                {"sid": active_site_id, "name": "Active Site"},
            )
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, 1, 0)"),
                {"sid": other_site_id, "name": "Other Site"},
            )
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, 2, 0)"),
                {"sid": foreign_site_id, "name": "Foreign Site"},
            )
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:did, :sid, :name, 'manual')"),
                {"did": active_dept, "sid": active_site_id, "name": "Active Site Department"},
            )
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:did, :sid, :name, 'manual')"),
                {"did": other_dept, "sid": other_site_id, "name": "Other Site Department"},
            )
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:did, :sid, :name, 'manual')"),
                {"did": foreign_dept, "sid": foreign_site_id, "name": "Foreign Tenant Department"},
            )
            db.commit()
        finally:
            db.close()
    return {
        "tenant_id": "1",
        "active_site_id": active_site_id,
        "other_site_id": other_site_id,
        "foreign_site_id": foreign_site_id,
        "active_department_id": active_dept,
        "other_department_id": other_dept,
        "foreign_department_id": foreign_dept,
        "foreign_tenant_id": str(foreign_tenant_id),
    }


def _current_admin_scope(client_admin) -> tuple[int, str]:
    with client_admin.session_transaction() as sess:
        tenant_id = int(sess.get("tenant_id") or 1)
        site_id = str(sess.get("site_id") or "").strip()
    assert site_id, "admin fixture must have an active site"
    return tenant_id, site_id


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
    assert "Admin User Test" in html
    assert "Staff User Test" in html


def test_users_list_shows_residence_department_label(client_admin):
    """Test user list scopes use residence + department labels."""
    app = client_admin.application
    _, active_site_id = _current_admin_scope(client_admin)
    dept_id = str(uuid.uuid4())
    _seed_unit_portal_department(
        app,
        tenant_id=1,
        site_id=active_site_id,
        department_id=dept_id,
        site_name="Centralköket",
        department_name="Avdelning 2",
        residence_name="Kaktusen",
    )
    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active, department_id) "
                    "VALUES (1, :email, 'hash', 'unit_portal', :username, 'List User', 1, :department_id)"
                ),
                {
                    "email": f"list-user-{uuid.uuid4().hex[:8]}@example.com",
                    "username": f"list-user-{uuid.uuid4().hex[:8]}",
                    "department_id": dept_id,
                },
            )
            db.commit()
        finally:
            db.close()

    resp = client_admin.get("/ui/admin/users", headers=_h("admin"))
    html = resp.data.decode("utf-8")

    assert resp.status_code == 200
    assert "Kaktusen \u2013 Avdelning 2" in html
    assert "Centralköket / Avdelning 2" not in html


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
    assert "Skapa användare" in html
    assert "Användarnamn" not in html
    assert "E-post" in html
    assert "Lösenord" in html
    assert "Admin" in html
    assert "Kök" in html
    assert "Avdelning" in html
    assert "Aktiv site" in html
    assert 'name="csrf_token"' in html


def test_users_new_form_limits_departments_to_active_site(client_admin):
    """Test the create form only shows departments from the active site."""
    app = client_admin.application
    _, active_site_id = _current_admin_scope(client_admin)
    other_site_id = f"{active_site_id}-other"
    foreign_site_id = f"{active_site_id}-foreign"
    ids = _seed_department_scope_matrix(
        app,
        active_site_id=active_site_id,
        other_site_id=other_site_id,
        foreign_site_id=foreign_site_id,
    )

    resp = client_admin.get("/ui/admin/users/new", headers=_h("admin"))
    html = resp.data.decode("utf-8")

    assert resp.status_code == 200
    assert "Active Site Department" in html
    assert "Other Site Department" not in html
    assert "Foreign Tenant Department" not in html
    assert "Skapa en avdelning först" not in html


def test_users_new_form_uses_residence_labels_for_departments(client_admin):
    """Test the department selector labels combine residence and department, not site and department."""
    app = client_admin.application
    _, active_site_id = _current_admin_scope(client_admin)
    dept_with_residence = str(uuid.uuid4())
    dept_other_residence = str(uuid.uuid4())
    dept_without_residence = str(uuid.uuid4())
    _seed_unit_portal_department(
        app,
        tenant_id=1,
        site_id=active_site_id,
        department_id=dept_with_residence,
        site_name="Centralköket",
        department_name="Avdelning 2",
        residence_name="Kaktusen",
    )
    _seed_unit_portal_department(
        app,
        tenant_id=1,
        site_id=active_site_id,
        department_id=dept_other_residence,
        site_name="Centralköket",
        department_name="Avdelning 9",
        residence_name="Solgläntan",
    )
    _seed_unit_portal_department(
        app,
        tenant_id=1,
        site_id=active_site_id,
        department_id=dept_without_residence,
        site_name="Centralköket",
        department_name="Avdelning 7",
    )

    resp = client_admin.get("/ui/admin/users/new", headers=_h("admin"))
    html = resp.data.decode("utf-8")

    assert resp.status_code == 200
    assert f'value="{dept_with_residence}"' in html
    assert f'value="{dept_other_residence}"' in html
    assert f'value="{dept_without_residence}"' in html
    assert "Kaktusen \u2013 Avdelning 2" in html
    assert "Solgläntan \u2013 Avdelning 9" in html
    assert "Avdelning 7" in html
    assert "Centralköket \u2013 Avdelning 2" not in html


def test_users_edit_form_shows_empty_state_when_active_site_has_no_departments(client_admin):
    """Test the unit_portal edit form stays empty-state when active site has no departments."""
    app = client_admin.application
    tenant_id, active_site_id = _current_admin_scope(client_admin)
    empty_site_id = f"{active_site_id}-empty"
    other_site_id = f"{active_site_id}-other-empty"
    foreign_site_id = f"{active_site_id}-foreign-empty"
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:tid, :name, 1)"), {"tid": tenant_id, "name": f"Tenant {tenant_id}"})
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, :tid, 0)"),
                {"sid": empty_site_id, "name": "Empty Active Site", "tid": tenant_id},
            )
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, :tid, 0)"),
                {"sid": other_site_id, "name": "Other Site With Departments", "tid": tenant_id},
            )
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES(:sid, :name, :tid, 0)"),
                {"sid": foreign_site_id, "name": "Foreign Tenant Site", "tid": 2},
            )
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:did, :sid, :name, 'manual')"),
                {"did": str(uuid.uuid4()), "sid": other_site_id, "name": "Other Site Department"},
            )
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:did, :sid, :name, 'manual')"),
                {"did": str(uuid.uuid4()), "sid": foreign_site_id, "name": "Foreign Tenant Department"},
            )
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active, department_id) "
                    "VALUES (:tid, :email, :ph, 'unit_portal', :username, :full_name, 1, NULL)"
                ),
                {
                    "tid": tenant_id,
                    "email": f"empty-{uuid.uuid4().hex[:8]}@example.com",
                    "ph": "hash",
                    "username": f"empty-{uuid.uuid4().hex[:8]}",
                    "full_name": "Empty Site User",
                },
            )
            db.commit()
            user_id = db.execute(text("SELECT id FROM users WHERE full_name = 'Empty Site User' LIMIT 1")).fetchone()[0]
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = empty_site_id

    resp = client_admin.get(f"/ui/admin/users/{user_id}/edit", headers=_h("admin"))
    html = resp.data.decode("utf-8")

    assert resp.status_code == 200
    assert "Skapa en avdelning först" in html
    assert "Other Site Department" not in html
    assert "Foreign Tenant Department" not in html


def test_users_edit_form_uses_same_residence_labels_as_create_form(client_admin):
    """Test the edit form uses the same canonical residence-plus-department labels."""
    app = client_admin.application
    _, active_site_id = _current_admin_scope(client_admin)
    dept_with_residence = str(uuid.uuid4())
    _seed_unit_portal_department(
        app,
        tenant_id=1,
        site_id=active_site_id,
        department_id=dept_with_residence,
        site_name="Centralköket",
        department_name="Avdelning 2",
        residence_name="Kaktusen",
    )

    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active, department_id) "
                    "VALUES (1, :email, 'hash', 'unit_portal', :username, 'Edit User', 1, :department_id)"
                ),
                {
                    "email": f"edit-user-{uuid.uuid4().hex[:8]}@example.com",
                    "username": f"edit-user-{uuid.uuid4().hex[:8]}",
                    "department_id": dept_with_residence,
                },
            )
            db.commit()
            user_id = db.execute(text("SELECT id FROM users WHERE department_id = :department_id ORDER BY id DESC LIMIT 1"), {"department_id": dept_with_residence}).fetchone()[0]
        finally:
            db.close()

    resp = client_admin.get(f"/ui/admin/users/{user_id}/edit", headers=_h("admin"))
    html = resp.data.decode("utf-8")

    assert resp.status_code == 200
    assert f'<option value="{dept_with_residence}" selected>Kaktusen \u2013 Avdelning 2</option>' in html
    assert f'<option value="{dept_with_residence}" selected>Centralköket \u2013 Avdelning 2</option>' not in html


def test_users_create_success(client_admin):
    """Test creating a new user"""
    app = client_admin.application
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    
    resp = client_admin.post("/ui/admin/users/new", data={
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
                text("SELECT username, email, role, is_active FROM users WHERE lower(email) = 'newuser_create@test.com'")
            ).fetchone()
            assert row is not None
            assert row[0] == "newuser_create@test.com"
            assert row[1] == "newuser_create@test.com"
            assert row[2] == "staff"
            assert row[3] == 1  # is_active
        finally:
            db.close()


def test_users_create_validates_required_fields(client_admin):
    """Test user creation requires email and password"""
    app = client_admin.application
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post("/ui/admin/users/new", data={
        "email": "test_validation@test.com",
        "role": "staff",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT id FROM users WHERE email = 'test_validation@test.com'")
            ).fetchone()
            assert row is None
        finally:
            db.close()


def test_users_create_invalid_csrf_rejected(client_admin):
    """Test invalid CSRF blocks user creation."""
    app = client_admin.application
    prev_strict = app.config.get("STRICT_CSRF_IN_TESTS")
    app.config["STRICT_CSRF_IN_TESTS"] = True
    resp = client_admin.post(
        "/ui/admin/users/new",
        data={
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
    """Test cannot create user with duplicate normalized email/username"""
    app = client_admin.application
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")

    create_resp = client_admin.post("/ui/admin/users/new", data={
        "email": "existing_dup_username@test.com",
        "password": "pass123",
        "role": "staff",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)
    assert create_resp.status_code == 200

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post("/ui/admin/users/new", data={
        "email": "Existing_Dup_Username@Test.com",
        "password": "pass123",
        "role": "staff",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)

    html = resp.data.decode("utf-8")
    assert "finns redan" in html.lower()
    with app.app_context():
        db = get_session()
        try:
            count = db.execute(
                text("SELECT COUNT(*) FROM users WHERE lower(email) = 'existing_dup_username@test.com'")
            ).fetchone()[0]
            assert count == 1
        finally:
            db.close()


def test_users_create_prevents_duplicate_email(client_admin):
    """Test cannot create user with duplicate email"""
    app = client_admin.application
    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    create_resp = client_admin.post("/ui/admin/users/new", data={
        "email": "existing_dup_email@test.com",
        "password": "pass123",
        "role": "staff",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)
    assert create_resp.status_code == 200

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post("/ui/admin/users/new", data={
        "email": "Existing_Dup_Email@Test.com",  # Already exists
        "password": "pass123",
        "role": "staff",
        "csrf_token": csrf_token,
    }, headers=_h("admin"), follow_redirects=True)

    assert resp.status_code == 200
    with app.app_context():
        db = get_session()
        try:
            count = db.execute(
                text("SELECT COUNT(*) FROM users WHERE lower(email) = 'existing_dup_email@test.com'")
            ).fetchone()[0]
            assert count == 1
        finally:
            db.close()


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
    _, active_site_id = _current_admin_scope(client_admin)
    dept_id = str(uuid.uuid4())
    email = f"portal_user_ok_{uuid.uuid4().hex[:8]}@test.com"
    _seed_unit_portal_department(app, tenant_id=1, site_id=active_site_id, department_id=dept_id)

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "username": "portal_user_ok",
            "email": email,
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
                text("SELECT role, department_id FROM users WHERE lower(email) = :email"),
                {"email": email.lower()},
            ).fetchone()
            assert row is not None
            assert row[0] == "unit_portal"
            assert row[1] == dept_id
        finally:
            db.close()


def test_users_create_unit_portal_uses_active_site_department_only(client_admin):
    """Test unit_portal create accepts an active-site department and rejects other-site choices."""
    app = client_admin.application
    _, active_site_id = _current_admin_scope(client_admin)
    other_site_id = f"{active_site_id}-other"
    foreign_site_id = f"{active_site_id}-foreign"
    ids = _seed_department_scope_matrix(
        app,
        active_site_id=active_site_id,
        other_site_id=other_site_id,
        foreign_site_id=foreign_site_id,
    )
    ok_email = f"portal_user_ok_{uuid.uuid4().hex[:8]}@test.com"
    other_email = f"portal_user_other_{uuid.uuid4().hex[:8]}@test.com"
    foreign_email = f"portal_user_foreign_{uuid.uuid4().hex[:8]}@test.com"

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    create_resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "email": ok_email,
            "full_name": "Portal User OK",
            "password": "password123",
            "role": "unit_portal",
            "department_id": ids["active_department_id"],
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    assert create_resp.status_code == 200
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT role, department_id, must_change_password FROM users WHERE lower(email) = :email"),
                {"email": ok_email.lower()},
            ).fetchone()
            assert row is not None
            assert row[0] == "unit_portal"
            assert row[1] == ids["active_department_id"]
            assert row[2] == 1
        finally:
            db.close()

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    other_site_resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "email": other_email,
            "full_name": "Portal User Other",
            "password": "password123",
            "role": "unit_portal",
            "department_id": ids["other_department_id"],
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    assert other_site_resp.status_code == 200
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM users WHERE lower(email) = :email"), {"email": other_email.lower()}).fetchone()
            assert row is None
        finally:
            db.close()

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    foreign_resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "email": foreign_email,
            "full_name": "Portal User Foreign",
            "password": "password123",
            "role": "unit_portal",
            "department_id": ids["foreign_department_id"],
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    assert foreign_resp.status_code == 200
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM users WHERE lower(email) = :email"), {"email": foreign_email.lower()}).fetchone()
            assert row is None
        finally:
            db.close()


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
    assert "Användarnamn" not in html
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
    _, active_site_id = _current_admin_scope(client_admin)
    other_site_id = f"{active_site_id}-edit-other"
    foreign_site_id = f"{active_site_id}-edit-foreign"
    ids = _seed_department_scope_matrix(
        app,
        active_site_id=active_site_id,
        other_site_id=other_site_id,
        foreign_site_id=foreign_site_id,
    )

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
                {"ph": pw_hash, "dept": ids["active_department_id"]},
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
            "department_id": ids["foreign_department_id"],
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
                text("SELECT role, department_id FROM users WHERE id = :uid"),
                {"uid": user_id},
            ).fetchone()
            assert row is not None
            assert row[0] == "unit_portal"
            assert row[1] == ids["active_department_id"]
        finally:
            db.close()

    csrf_token = _form_csrf(client_admin, f"/ui/admin/users/{user_id}/edit")
    resp = client_admin.post(
        f"/ui/admin/users/{user_id}/edit",
        data={
            "email": "updated@test.com",
            "full_name": "Updated Name",
            "role": "cook",
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
                text("SELECT email, full_name, role FROM users WHERE id = :uid"),
                {"uid": user_id},
            ).fetchone()
            assert row[0] == "updated@test.com"
            assert row[1] == "Updated Name"
            assert row[2] == "cook"
        finally:
            db.close()


def test_users_update_unit_portal_rejects_same_tenant_other_site_department(client_admin):
    """Test editing a unit_portal user cannot move them to another site in the same tenant."""
    app = client_admin.application
    _, active_site_id = _current_admin_scope(client_admin)
    other_site_id = f"{active_site_id}-edit-same-tenant"
    foreign_site_id = f"{active_site_id}-edit-foreign-2"
    ids = _seed_department_scope_matrix(
        app,
        active_site_id=active_site_id,
        other_site_id=other_site_id,
        foreign_site_id=foreign_site_id,
    )

    with app.app_context():
        db = get_session()
        try:
            from werkzeug.security import generate_password_hash

            pw_hash = generate_password_hash("pass123")
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active, department_id) "
                    "VALUES (1, 'portal_same_site_edit@test.com', :ph, 'unit_portal', 'portal_same_site_edit_user', 'Portal Same Site Edit User', 1, :dept)"
                ),
                {"ph": pw_hash, "dept": ids["active_department_id"]},
            )
            db.commit()
            user_id = db.execute(text("SELECT id FROM users WHERE username = 'portal_same_site_edit_user' LIMIT 1")).fetchone()[0]
        finally:
            db.close()

    csrf_token = _form_csrf(client_admin, f"/ui/admin/users/{user_id}/edit")
    resp = client_admin.post(
        f"/ui/admin/users/{user_id}/edit",
        data={
            "email": "portal_same_site_edit@test.com",
            "full_name": "Portal Same Site Edit User",
            "role": "unit_portal",
            "department_id": ids["other_department_id"],
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
                text("SELECT role, department_id FROM users WHERE id = :uid"),
                {"uid": user_id},
            ).fetchone()
            assert row is not None
            assert row[0] == "unit_portal"
            assert row[1] == ids["active_department_id"]
        finally:
            db.close()


def test_users_create_unit_portal_rejects_cross_tenant_department(client_admin):
    """Test unit_portal create rejects departments from another tenant."""
    app = client_admin.application
    _, active_site_id = _current_admin_scope(client_admin)
    ids = _seed_department_scope_matrix(
        app,
        active_site_id=active_site_id,
        other_site_id=f"{active_site_id}-other-ct",
        foreign_site_id=f"{active_site_id}-foreign-ct",
    )

    csrf_token = _form_csrf(client_admin, "/ui/admin/users/new")
    resp = client_admin.post(
        "/ui/admin/users/new",
        data={
            "email": "portal_user_bad@test.com",
            "full_name": "Portal User Bad",
            "password": "password123",
            "role": "unit_portal",
            "department_id": ids["foreign_department_id"],
            "csrf_token": csrf_token,
        },
        headers=_h("admin"),
        follow_redirects=True,
    )

    assert resp.status_code == 200
    with app.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM users WHERE lower(email) = 'portal_user_bad@test.com'")).fetchone()
            assert row is None
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
