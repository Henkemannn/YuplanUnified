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


def _seed_quick_overview_fixture(site_name: str = "Quick overview site"):
    from core.admin_repo import DepartmentServiceAddonsRepo, DepartmentsRepo, DietTypesRepo, ServiceAddonsRepo, SitesRepo
    from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo

    site, _ = SitesRepo().create_site(f"{site_name} {uuid.uuid4()}")
    fixed_dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avdelning A",
        resident_count_mode="fixed",
        resident_count_fixed=12,
    )
    variable_dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avdelning 2",
        resident_count_mode="per_day_meal",
        resident_count_fixed=0,
    )

    primary_req = DietTypesRepo().create(site_id=site["id"], name="Primär special", default_select=False, semantics="atomic")
    modifier_req = DietTypesRepo().create(site_id=site["id"], name="Modifier special", default_select=False, semantics="atomic")
    DepartmentRequirementGroupsRepo().save_group(
        department_id=fixed_dept["id"],
        default_quantity=3,
        requirement_ids=[modifier_req, primary_req],
        primary_requirement_id=primary_req,
        label=None,
    )

    addon_repo = ServiceAddonsRepo()
    addon_id = addon_repo.create_if_missing("Mos vid sidan", site_id=site["id"], addon_family="mos")
    DepartmentServiceAddonsRepo().add_for_department(
        fixed_dept["id"],
        addon_id,
        service_scope="all_services",
        quantity_mode="whole_department",
        lunch_count=None,
        dinner_count=None,
        note="Serveras endast vid behov",
        site_id=site["id"],
    )

    return {
        "site": site,
        "fixed_dept": fixed_dept,
        "variable_dept": variable_dept,
        "primary_req": primary_req,
        "modifier_req": modifier_req,
        "addon_id": addon_id,
    }


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
    assert "25 boende" in html
    assert "Boende / enhet" in html
    assert "Ej valt" in html
    assert "Redigera" in html
    assert "/ui/admin/departments/" in html
    assert "/ui/admin/departments/" in html and "/edit" in html
    assert "TestSite •" not in html
    assert "app-shell__page-header" in html
    assert "app-shell__grid" in html
    assert "app-shell__card" in html
    assert "app-shell__list-item" in html


def test_departments_list_uses_secondary_overflow_actions(client_admin):
    """Test list rows keep ordering and delete inside secondary overflow controls."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    fixed_dept_id = str(uuid.uuid4())
    variable_dept_id = str(uuid.uuid4())
    residence_id = str(uuid.uuid4())

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO tenants (id, name, active) VALUES (1, 'Tenant', 1)"))
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.execute(text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"), {"id": residence_id, "sid": site_id, "name": "Kaktusen"})
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',12,1,0)"
                ),
                {"i": fixed_dept_id, "s": site_id, "r": residence_id, "n": "Avdelning 1"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'per_day_meal',0,2,0)"
                ),
                {"i": variable_dept_id, "s": site_id, "r": residence_id, "n": "Avdelning 2"},
            )
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    html = resp.data.decode("utf-8")

    assert resp.status_code == 200
    assert "Avdelning 1" in html
    assert "Avdelning 2" in html
    assert "12 boende" in html
    assert "Varierat boendeantal" in html
    assert "Boende / enhet" in html
    assert "Redigera" in html
    assert "data-department-drag-handle" in html
    assert "Klicka på avdelningsnamnet för snabböversikt. Redigera för att göra ändringar." in html
    assert 'data-department-quick-overview-trigger' in html
    assert 'data-department-quick-overview-url="' in html
    assert 'data-department-quick-overview-panel' in html
    assert "Snabböversikt" in html
    assert "Välj en avdelning för att se information." in html
    assert "Spara ordning" not in html
    assert 'name="display_order"' not in html
    assert "display_order_" not in html
    assert "Ta bort avdelning" in html
    assert 'data-modal-target="#department-delete-modal"' in html
    assert 'data-department-delete-form' in html
    assert 'name="confirmation"' in html
    assert 'data-department-delete-confirm-button' in html
    assert 'name="resident_count"' not in html
    assert 'admin-departments__delete-form' not in html
    assert "app-shell__list-link" not in html
    assert "/edit" in html


def test_department_quick_overview_route_renders_shared_summary_and_variable_counts(client_admin):
    data = _seed_quick_overview_fixture()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = data["site"]["id"]

    fixed_resp = client_admin.get(
        f"/ui/admin/departments/{data['fixed_dept']['id']}/quick-overview",
        headers=_h("admin"),
    )
    assert fixed_resp.status_code == 200
    fixed_html = fixed_resp.data.decode("utf-8")
    assert "Avdelning A" in fixed_html
    assert "Boende / enhet" in fixed_html
    assert "12 boende" in fixed_html
    assert "Primär special" in fixed_html
    assert "Modifier special" in fixed_html
    assert fixed_html.index("Primär special") < fixed_html.index("Modifier special")
    assert "Mos vid sidan" in fixed_html
    assert "Alla serveringar" in fixed_html
    assert "Hela avdelningen" in fixed_html
    assert "Serveras endast vid behov" in fixed_html
    assert "1 grupp" in fixed_html
    assert "1 anpassning" in fixed_html
    assert "Redigera avdelning" in fixed_html

    variable_resp = client_admin.get(
        f"/ui/admin/departments/{data['variable_dept']['id']}/quick-overview",
        headers=_h("admin"),
    )
    assert variable_resp.status_code == 200
    variable_html = variable_resp.data.decode("utf-8")
    assert "Varierar per dag/måltid" in variable_html
    assert "0 boende" not in variable_html
    assert "Redigera avdelning" in variable_html


def test_department_quick_overview_route_is_site_scoped(client_admin):
    data = _seed_quick_overview_fixture("Scoped overview")
    from core.admin_repo import DepartmentsRepo, SitesRepo

    other_site, _ = SitesRepo().create_site(f"Foreign overview {uuid.uuid4()}")
    foreign_dept, _ = DepartmentsRepo().create_department(
        site_id=other_site["id"],
        name="Foreign Dept",
        resident_count_mode="fixed",
        resident_count_fixed=9,
    )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = data["site"]["id"]

    foreign_resp = client_admin.get(
        f"/ui/admin/departments/{foreign_dept['id']}/quick-overview",
        headers=_h("admin"),
    )
    assert foreign_resp.status_code == 404

    missing_resp = client_admin.get(
        f"/ui/admin/departments/{uuid.uuid4()}/quick-overview",
        headers=_h("admin"),
    )
    assert missing_resp.status_code == 404


def test_departments_reorder_batches_update_site_scoped_display_order(client_admin):
    """Test drag reorder persists canonical site-scoped display_order values."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    other_site_id = str(uuid.uuid4())
    residence_id = str(uuid.uuid4())
    foreign_residence_id = str(uuid.uuid4())
    dept_a = str(uuid.uuid4())
    dept_b = str(uuid.uuid4())
    dept_c = str(uuid.uuid4())
    foreign_dept = str(uuid.uuid4())

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": other_site_id, "name": "OtherSite"})
            db.execute(text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"), {"id": residence_id, "sid": site_id, "name": "Kaktusen"})
            db.execute(text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"), {"id": foreign_residence_id, "sid": other_site_id, "name": "Solrosen"})
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',11,1,0)"
                ),
                {"i": dept_a, "s": site_id, "r": residence_id, "n": "Avdelning A"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',12,2,0)"
                ),
                {"i": dept_b, "s": site_id, "r": residence_id, "n": "Avdelning B"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',13,3,0)"
                ),
                {"i": dept_c, "s": site_id, "r": residence_id, "n": "Avdelning C"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',10,1,0)"
                ),
                {"i": foreign_dept, "s": other_site_id, "r": foreign_residence_id, "n": "Foreign Dept"},
            )
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.post(
        "/ui/admin/departments/reorder",
        headers=_h("admin"),
        json={"department_ids": [dept_c, dept_a, dept_b]},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    assert payload["ok"] is True
    assert payload["department_ids"] == [dept_c, dept_a, dept_b]
    assert payload["display_orders"] == [1, 2, 3]

    with app.app_context():
        db = get_session()
        try:
            rows = db.execute(
                text("SELECT id, display_order FROM departments WHERE site_id=:sid ORDER BY display_order, name"),
                {"sid": site_id},
            ).fetchall()
            foreign_row = db.execute(
                text("SELECT display_order FROM departments WHERE id=:id"),
                {"id": foreign_dept},
            ).fetchone()
        finally:
            db.close()

    assert [row[0] for row in rows] == [dept_c, dept_a, dept_b]
    assert [int(row[1]) for row in rows] == [1, 2, 3]
    assert foreign_row is not None
    assert int(foreign_row[0] or 0) == 1

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    assert html.index("Avdelning C") < html.index("Avdelning A") < html.index("Avdelning B")


def test_departments_reorder_rejects_duplicate_unknown_and_foreign_departments(client_admin):
    """Test batch reorder rejects invalid department sets."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    other_site_id = str(uuid.uuid4())
    residence_id = str(uuid.uuid4())
    other_residence_id = str(uuid.uuid4())
    dept_a = str(uuid.uuid4())
    dept_b = str(uuid.uuid4())
    foreign_dept = str(uuid.uuid4())
    unknown_dept = str(uuid.uuid4())

    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": other_site_id, "name": "OtherSite"})
            db.execute(text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"), {"id": residence_id, "sid": site_id, "name": "Kaktusen"})
            db.execute(text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"), {"id": other_residence_id, "sid": other_site_id, "name": "Solrosen"})
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',11,1,0)"
                ),
                {"i": dept_a, "s": site_id, "r": residence_id, "n": "Avdelning A"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',12,2,0)"
                ),
                {"i": dept_b, "s": site_id, "r": residence_id, "n": "Avdelning B"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, display_order, version) "
                    "VALUES(:i,:s,:r,:n,'fixed',10,1,0)"
                ),
                {"i": foreign_dept, "s": other_site_id, "r": other_residence_id, "n": "Foreign Dept"},
            )
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    duplicate_resp = client_admin.post(
        "/ui/admin/departments/reorder",
        headers=_h("admin"),
        json={"department_ids": [dept_a, dept_a]},
    )
    assert duplicate_resp.status_code == 400

    foreign_resp = client_admin.post(
        "/ui/admin/departments/reorder",
        headers=_h("admin"),
        json={"department_ids": [dept_a, foreign_dept]},
    )
    assert foreign_resp.status_code == 400

    unknown_resp = client_admin.post(
        "/ui/admin/departments/reorder",
        headers=_h("admin"),
        json={"department_ids": [dept_a, unknown_dept]},
    )
    assert unknown_resp.status_code == 400

    with app.app_context():
        db = get_session()
        try:
            rows = db.execute(
                text("SELECT id, display_order FROM departments WHERE site_id=:sid ORDER BY display_order, name"),
                {"sid": site_id},
            ).fetchall()
        finally:
            db.close()

    assert [row[0] for row in rows] == [dept_a, dept_b]
    assert [int(row[1]) for row in rows] == [1, 2]


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
    assert "+ Ny avdelning" in html
    assert "/ui/admin/departments/new" in html


def test_departments_list_empty_state(client_admin):
    """Test departments list shows empty state when no departments."""
    resp = client_admin.get("/ui/admin/departments", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    # Should show empty state message
    assert "Inga avdelningar ännu." in html or "+ Ny avdelning" in html


# ============================================================================
# Department Create Tests
# ============================================================================

def test_departments_new_form_happy_path(client_admin):
    """Test new department form renders correctly."""
    app = client_admin.application
    site_id = str(uuid.uuid4())
    from core.db import create_all, get_session
    from sqlalchemy import text

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.get("/ui/admin/departments/new", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    
    assert resp.status_code == 200
    assert "Ny avdelning" in html
    assert html.count("Kund:") == 1
    assert html.count("Arbetsplats:") == 1
    assert "Vecka " not in html
    assert 'name="name"' in html
    assert 'name="residence_id"' in html
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
    residence_id = str(uuid.uuid4())
    user_id = 1
    notes_text = "Skapad med anteckning"
    
    # Seed site
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            db.execute(
                text("INSERT INTO residences (id, site_id, name) VALUES(:id, :sid, :name)"),
                {"id": residence_id, "sid": site_id, "name": "Boende A"},
            )
            # Update test user to have this site
            
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    
    # Create department
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "New Test Department",
            "residence_id": residence_id,
            "resident_count": "30",
            "notes": notes_text,
        },
        follow_redirects=True
    )
    
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Should redirect to list with success message
    assert "New Test Department" in html or "skapad" in html

    with app.app_context():
        db = get_session()
        try:
            dept_row = db.execute(
                text("SELECT id, notes, residence_id FROM departments WHERE name = :name AND site_id = :sid"),
                {"name": "New Test Department", "sid": site_id},
            ).fetchone()
        finally:
            db.close()

    assert dept_row is not None
    dept_id, saved_notes, saved_residence_id = dept_row[0], dept_row[1], dept_row[2]
    assert saved_notes == notes_text
    assert saved_residence_id == residence_id

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    resp = client_admin.get(f"/ui/admin/departments/{dept_id}/edit", headers=_h("admin"))
    html = resp.data.decode("utf-8")
    assert notes_text in html


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

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    
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
    residence_id = str(uuid.uuid4())
    user_id = 1
    
    # Seed site
    from core.db import create_all, get_session
    from sqlalchemy import text
    
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text(f"INSERT INTO sites (id, name, version) VALUES ('{site_id}', 'TestSite', 0)"))
            db.execute(
                text("INSERT INTO residences (id, site_id, name) VALUES(:id, :sid, :name)"),
                {"id": residence_id, "sid": site_id, "name": "Boende A"},
            )
            
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
    
    # Try to create with negative residents
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "Test Dept",
            "residence_id": residence_id,
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
    assert "app-shell__env-badge" in html
    assert "TestSite" in html
    assert '<div class="app-shell__card-meta">Vecka ' not in html


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

def _seed_department_delete_fixture(
    app,
    *,
    include_contract_rows: bool = False,
    include_foreign_department: bool = False,
    add_delete_trigger: bool = False,
):
    from core.db import create_all, get_session
    from sqlalchemy import text

    site_id = str(uuid.uuid4())
    residence_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    foreign_site_id = str(uuid.uuid4()) if include_foreign_department else None
    foreign_residence_id = str(uuid.uuid4()) if include_foreign_department else None
    foreign_dept_id = str(uuid.uuid4()) if include_foreign_department else None

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.execute(
                text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"),
                {"id": residence_id, "sid": site_id, "name": "Boende A"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, notes, display_order, version) "
                    "VALUES(:id,:sid,:rid,:name,'fixed',10,'Test note',1,0)"
                ),
                {"id": dept_id, "sid": site_id, "rid": residence_id, "name": "Delete Me"},
            )
            db.execute(
                text(
                    "INSERT INTO users(id, tenant_id, username, email, password_hash, auth_version, must_change_password, role, is_active, department_id) "
                    "VALUES(1001, 1, 'dept-admin', 'dept-admin@example.com', 'hash', 1, 0, 'admin', 1, :department_id)"
                ),
                {"department_id": dept_id},
            )

            if include_foreign_department:
                db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": foreign_site_id, "name": "ForeignSite"})
                db.execute(
                    text("INSERT INTO residences (id, site_id, name) VALUES (:id, :sid, :name)"),
                    {"id": foreign_residence_id, "sid": foreign_site_id, "name": "ForeignBoende"},
                )
                db.execute(
                    text(
                        "INSERT INTO departments(id, site_id, residence_id, name, resident_count_mode, resident_count_fixed, version) "
                        "VALUES(:id,:sid,:rid,:name,'fixed',5,0)"
                    ),
                    {"id": foreign_dept_id, "sid": foreign_site_id, "rid": foreign_residence_id, "name": "Foreign Dept"},
                )

            if include_contract_rows:
                db.execute(text("CREATE TABLE IF NOT EXISTS department_residents_schedule (department_id TEXT NOT NULL, week INTEGER, weekday INTEGER NOT NULL, meal TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(department_id, week, weekday, meal))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_residents_weekly (id TEXT PRIMARY KEY, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, residents_lunch INTEGER NULL, residents_dinner INTEGER NULL, updated_at TEXT)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_defaults (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, default_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(department_id, diet_type_id))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_diet_overrides (department_id TEXT NOT NULL, diet_type_id TEXT NOT NULL, day INTEGER NOT NULL, meal TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, updated_at TEXT, PRIMARY KEY(department_id, diet_type_id, day, meal))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_service_addons (id TEXT PRIMARY KEY, department_id TEXT NOT NULL, addon_id TEXT NOT NULL, lunch_count INTEGER NULL, dinner_count INTEGER NULL, note TEXT NULL, created_at TEXT, service_scope TEXT, quantity_mode TEXT)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_menu_choices (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, weekday INTEGER NOT NULL, meal TEXT NOT NULL, selected_variant TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_menu_row_demands (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, weekday INTEGER NOT NULL, builder_menu_id TEXT NOT NULL, builder_menu_version INTEGER NOT NULL, builder_menu_row_id TEXT NOT NULL, selection_group_id TEXT NULL, quantity INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_portal_week_submissions (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, builder_menu_id TEXT NOT NULL, builder_menu_version INTEGER NOT NULL, choice_signature TEXT NOT NULL, submitted_at TEXT, updated_at TEXT)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS alt2_flags (site_id TEXT NOT NULL, department_id TEXT NOT NULL, week INTEGER NOT NULL, weekday INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0, updated_at TEXT, PRIMARY KEY(site_id, department_id, week, weekday))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS weekview_alt2_flags (site_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, day_of_week INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 0, UNIQUE(site_id, department_id, year, week, day_of_week))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_notes (department_id TEXT PRIMARY KEY, notes TEXT)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS weekview_registrations (tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, diet_type TEXT, marked INTEGER, UNIQUE(tenant_id, department_id, year, week, day_of_week, meal, diet_type))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS weekview_residents_count (tenant_id TEXT, department_id TEXT, year INTEGER, week INTEGER, day_of_week INTEGER, meal TEXT, count INTEGER, UNIQUE(tenant_id, department_id, year, week, day_of_week, meal))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_requirement_groups (id TEXT PRIMARY KEY, department_id TEXT NOT NULL, label TEXT NULL, default_quantity INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT, primary_requirement_id INTEGER NULL)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_requirement_group_requirements (group_id TEXT NOT NULL, dietary_type_id INTEGER NOT NULL, PRIMARY KEY(group_id, dietary_type_id))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_requirement_group_service_overrides (group_id TEXT NOT NULL, service_date TEXT NOT NULL, meal_key TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT, PRIMARY KEY(group_id, service_date, meal_key))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_requirement_group_completions (group_id TEXT NOT NULL, service_date TEXT NOT NULL, meal_key TEXT NOT NULL, marked INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(group_id, service_date, meal_key))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS department_requirement_group_weekday_overrides (group_id TEXT NOT NULL, weekday INTEGER NOT NULL, meal_key TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(group_id, weekday, meal_key))"))
                db.execute(text("CREATE TABLE IF NOT EXISTS planning_option_reviews (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, service_date TEXT NOT NULL, meal TEXT NOT NULL, builder_menu_id TEXT NOT NULL, builder_menu_version INTEGER NOT NULL, builder_menu_row_id TEXT NOT NULL, review_basis_version INTEGER NOT NULL DEFAULT 1, review_basis_hash TEXT NOT NULL, reviewed_by_user_id INTEGER NOT NULL, reviewed_at TEXT NOT NULL, completed_at TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
                db.execute(text("CREATE TABLE IF NOT EXISTS planning_option_review_decisions (id INTEGER PRIMARY KEY, review_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, destination_id TEXT NOT NULL, requirement_group_id TEXT NOT NULL, decision TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"))

                group_id = str(uuid.uuid4())
                db.execute(text("INSERT INTO department_residents_schedule(department_id, week, weekday, meal, count) VALUES(:d, 1, 1, 'lunch', 11)"), {"d": dept_id})
                db.execute(text("INSERT INTO department_residents_weekly(id, department_id, year, week, residents_lunch, residents_dinner, updated_at) VALUES(:id, :d, 2026, 41, 9, 8, '2026-10-10 12:00:00')"), {"id": str(uuid.uuid4()), "d": dept_id})
                db.execute(text("INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d, 'diet-1', 2)"), {"d": dept_id})
                db.execute(text("INSERT INTO department_diet_overrides(department_id, diet_type_id, day, meal, count, updated_at) VALUES(:d, 'diet-1', 1, 'lunch', 3, '2026-10-10 12:00:00')"), {"d": dept_id})
                db.execute(text("INSERT INTO department_service_addons(id, department_id, addon_id, lunch_count, dinner_count, note, created_at, service_scope, quantity_mode) VALUES(:id, :d, 'addon-1', 1, 2, 'note', '2026-10-10 12:00:00', 'whole_department', 'whole_department')"), {"id": str(uuid.uuid4()), "d": dept_id})
                db.execute(text("INSERT INTO department_menu_choices(id, tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES(1, 1, :sid, :d, 2026, 41, 1, 'lunch', 'alt1', 1, '2026-10-10 12:00:00', '2026-10-10 12:00:00')"), {"sid": site_id, "d": dept_id})
                db.execute(text("INSERT INTO department_menu_row_demands(id, tenant_id, site_id, department_id, year, week, weekday, builder_menu_id, builder_menu_version, builder_menu_row_id, selection_group_id, quantity, created_at, updated_at) VALUES(1, 1, :sid, :d, 2026, 41, 1, 'menu-1', 1, 'row-1', NULL, 5, '2026-10-10 12:00:00', '2026-10-10 12:00:00')"), {"sid": site_id, "d": dept_id})
                db.execute(text("INSERT INTO department_portal_week_submissions(id, tenant_id, site_id, department_id, year, week, builder_menu_id, builder_menu_version, choice_signature, submitted_at, updated_at) VALUES(1, 1, :sid, :d, 2026, 41, 'menu-1', 1, 'sig', '2026-10-10 12:00:00', '2026-10-10 12:00:00')"), {"sid": site_id, "d": dept_id})
                db.execute(text("INSERT INTO alt2_flags(site_id, department_id, week, weekday, enabled, version, updated_at) VALUES(:sid, :d, 41, 1, 1, 1, '2026-10-10 12:00:00')"), {"sid": site_id, "d": dept_id})
                db.execute(text("INSERT INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled) VALUES(:sid, :d, 2026, 41, 1, 1)"), {"sid": site_id, "d": dept_id})
                db.execute(text("INSERT INTO department_notes(department_id, notes) VALUES(:d, 'note')"), {"d": dept_id})
                db.execute(text("INSERT INTO weekview_registrations(tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked) VALUES('1', :d, 2026, 41, 1, 'lunch', 'diet-1', 1)"), {"d": dept_id})
                db.execute(text("INSERT INTO weekview_residents_count(tenant_id, department_id, year, week, day_of_week, meal, count) VALUES('1', :d, 2026, 41, 1, 'lunch', 14)"), {"d": dept_id})
                db.execute(text("INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at, primary_requirement_id) VALUES(:id, :d, 'Group', 0, 1, '2026-10-10 12:00:00', '2026-10-10 12:00:00', NULL)"), {"id": group_id, "d": dept_id})
                db.execute(text("INSERT INTO dietary_types (id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, 1, :sid, 'Diet 1', NULL, 'diet-1', 'atomic', 0)"), {"sid": site_id})
                db.execute(text("INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES(:gid, 1)"), {"gid": group_id})
                db.execute(text("INSERT INTO department_requirement_group_service_overrides(group_id, service_date, meal_key, quantity, created_at, updated_at) VALUES(:gid, '2026-10-10', 'lunch', 3, '2026-10-10 12:00:00', '2026-10-10 12:00:00')"), {"gid": group_id})
                db.execute(text("INSERT INTO department_requirement_group_completions(group_id, service_date, meal_key, marked) VALUES(:gid, '2026-10-10', 'lunch', 1)"), {"gid": group_id})
                db.execute(text("INSERT INTO department_requirement_group_weekday_overrides(group_id, weekday, meal_key, quantity) VALUES(:gid, 1, 'lunch', 7)"), {"gid": group_id})
                db.execute(text("INSERT INTO planning_option_reviews(id, tenant_id, site_id, service_date, meal, builder_menu_id, builder_menu_version, builder_menu_row_id, review_basis_version, review_basis_hash, reviewed_by_user_id, reviewed_at, completed_at, created_at, updated_at) VALUES(1, 1, :sid, '2026-10-10', 'lunch', 'menu-1', 1, 'row-1', 1, 'hash', 1001, '2026-10-10 12:00:00', '2026-10-10 12:00:00', '2026-10-10 12:00:00', '2026-10-10 12:00:00')"), {"sid": site_id})
                db.execute(text("INSERT INTO planning_option_review_decisions(id, review_id, tenant_id, destination_id, requirement_group_id, decision, created_at, updated_at) VALUES(1, 1, 1, :d, :gid, 'NO_ADAPTATION_REQUIRED', '2026-10-10 12:00:00', '2026-10-10 12:00:00')"), {"d": dept_id, "gid": group_id})
                if add_delete_trigger:
                    db.execute(text("CREATE TRIGGER fail_department_service_addons_delete BEFORE DELETE ON department_service_addons BEGIN SELECT RAISE(ABORT, 'boom'); END;"))

            db.commit()
        finally:
            db.close()

    return {
        "site_id": site_id,
        "residence_id": residence_id,
        "dept_id": dept_id,
        "foreign_site_id": foreign_site_id,
        "foreign_dept_id": foreign_dept_id,
    }


def test_departments_delete_happy_path(client_admin):
    """Test deleting a department with confirmation and child cleanup."""
    app = client_admin.application
    ids = _seed_department_delete_fixture(app, include_contract_rows=True)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = ids["site_id"]
    resp = client_admin.post(
        f"/ui/admin/departments/{ids['dept_id']}/delete",
        headers=_h("admin"),
        data={"confirmation": "Delete Me"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "borttagen" in html

    from core.db import get_session
    from sqlalchemy import text

    with app.app_context():
        db = get_session()
        try:
            assert db.execute(text("SELECT COUNT(*) FROM departments WHERE id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT department_id FROM users WHERE id=1001")).fetchone()[0] is None
            assert db.execute(text("SELECT COUNT(*) FROM department_residents_schedule WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_residents_weekly WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_diet_defaults WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_diet_overrides WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_service_addons WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_menu_choices WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_menu_row_demands WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_portal_week_submissions WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM alt2_flags WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM weekview_alt2_flags WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_notes WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM weekview_registrations WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM weekview_residents_count WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM department_requirement_groups WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
            assert db.execute(text("SELECT COUNT(*) FROM planning_option_review_decisions WHERE destination_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 0
        finally:
            db.close()


def test_departments_delete_requires_exact_confirmation(client_admin):
    """Test missing or wrong confirmation does not delete anything."""
    app = client_admin.application
    ids = _seed_department_delete_fixture(app)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = ids["site_id"]

    missing_resp = client_admin.post(
        f"/ui/admin/departments/{ids['dept_id']}/delete",
        headers=_h("admin"),
        data={},
        follow_redirects=True,
    )
    assert "Skriv avdelningens namn" in missing_resp.data.decode("utf-8")

    wrong_resp = client_admin.post(
        f"/ui/admin/departments/{ids['dept_id']}/delete",
        headers=_h("admin"),
        data={"confirmation": "Fel namn"},
        follow_redirects=True,
    )
    assert "Bekräftelsen matchar inte avdelningens namn." in wrong_resp.data.decode("utf-8")

    from core.db import get_session
    from sqlalchemy import text

    with app.app_context():
        db = get_session()
        try:
            assert db.execute(text("SELECT COUNT(*) FROM departments WHERE id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 1
            assert db.execute(text("SELECT department_id FROM users WHERE id=1001")).fetchone()[0] == ids["dept_id"]
        finally:
            db.close()


def test_departments_delete_rejects_foreign_site_department(client_admin):
    """Test a department from another site cannot be deleted."""
    app = client_admin.application
    ids = _seed_department_delete_fixture(app, include_foreign_department=True)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = ids["site_id"]

    resp = client_admin.post(
        f"/ui/admin/departments/{ids['foreign_dept_id']}/delete",
        headers=_h("admin"),
        data={"confirmation": "Foreign Dept"},
        follow_redirects=True,
    )
    assert "Bekräftelsen matchar inte avdelningens namn." in resp.data.decode("utf-8")

    from core.db import get_session
    from sqlalchemy import text

    with app.app_context():
        db = get_session()
        try:
            assert db.execute(text("SELECT COUNT(*) FROM departments WHERE id=:id"), {"id": ids["foreign_dept_id"]}).fetchone()[0] == 1
            assert db.execute(text("SELECT COUNT(*) FROM departments WHERE id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 1
        finally:
            db.close()


def test_departments_delete_rolls_back_on_failure(client_admin):
    """Test a cleanup failure rolls back parent and child changes."""
    app = client_admin.application
    ids = _seed_department_delete_fixture(app, include_contract_rows=True, add_delete_trigger=True)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = ids["site_id"]

    resp = client_admin.post(
        f"/ui/admin/departments/{ids['dept_id']}/delete",
        headers=_h("admin"),
        data={"confirmation": "Delete Me"},
        follow_redirects=True,
    )
    assert "boom" in resp.data.decode("utf-8")

    from core.db import get_session
    from sqlalchemy import text

    with app.app_context():
        db = get_session()
        try:
            assert db.execute(text("SELECT COUNT(*) FROM departments WHERE id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 1
            assert db.execute(text("SELECT department_id FROM users WHERE id=1001")).fetchone()[0] == ids["dept_id"]
            assert db.execute(text("SELECT COUNT(*) FROM department_residents_schedule WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 1
            assert db.execute(text("SELECT COUNT(*) FROM department_service_addons WHERE department_id=:id"), {"id": ids["dept_id"]}).fetchone()[0] == 1
        finally:
            db.close()


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
