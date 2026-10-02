from __future__ import annotations

from datetime import date as _date

from core.db import get_session
from core.admin_repo import DepartmentServiceAddonsRepo, ServiceAddonsRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.residents_weekly_repo import ResidentsWeeklyRepo
from sqlalchemy import text


YEAR = 2026
WEEK = 40
SITE_ID = "portal-home-site"
DEPT_ID = "portal-home-dept"


def _h():
    return {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_requirement_group(site_id: str, department_id: str) -> None:
    db = get_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (101, 1, :site_id, 'Timbal', 'Textur', 'timbal', 'atomic', 0)"),
            {"site_id": site_id},
        )
        db.execute(
            text("INSERT OR REPLACE INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (102, 1, :site_id, 'Glutenfri', 'Allergi / Exkludering', 'glutenfri', 'atomic', 0)"),
            {"site_id": site_id},
        )
        DepartmentRequirementGroupsRepo().create_group(department_id, 2, [101, 102], label=None, primary_requirement_id=101)
    finally:
        db.close()


def _seed_duplicate_requirement_label_group(site_id: str, department_id: str) -> None:
    db = get_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO dietary_types(id, tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (201, 1, :site_id, 'Glutenfri', 'Allergi / Exkludering', 'glutenfri-dup', 'atomic', 0)"),
            {"site_id": site_id},
        )
        DepartmentRequirementGroupsRepo().create_group(department_id, 4, [201], label="Glutenfri", primary_requirement_id=201)
    finally:
        db.close()


def _seed_service_addon(site_id: str, department_id: str) -> None:
    addon_id = ServiceAddonsRepo().create_if_missing("Sallad", site_id=site_id, addon_family="sallad")
    DepartmentServiceAddonsRepo().replace_for_department(
        department_id,
        [{"addon_id": addon_id, "lunch_count": 6, "note": "aldrig tomat"}],
        site_id=site_id,
    )


def _seed_publication(seed_canonical_builder_publication, *, site_id: str, year: int, week: int, alt1_name: str = "Pannbiff", alt2_name: str = "Fiskgratäng") -> None:
    seed_canonical_builder_publication(
        site_id=site_id,
        year=year,
        week=week,
        alt1_name=alt1_name,
        alt2_name=alt2_name,
        dessert_name="Fruktsallad",
        dinner_name="Kvällsgröt",
    )


def _seed_home_state(client_admin, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK, note="Privat notering")
    _seed_requirement_group(SITE_ID, DEPT_ID)
    _seed_service_addon(SITE_ID, DEPT_ID)
    ResidentsWeeklyRepo().upsert_for_week(DEPT_ID, YEAR, WEEK, 12, 12)

    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=39)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=40)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=41)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=42)

    db = get_session()
    try:
        db.execute(text("DELETE FROM department_menu_choices WHERE department_id=:department_id AND year=:year AND week=:week"), {"department_id": DEPT_ID, "year": YEAR, "week": 40})
        db.execute(text("DELETE FROM department_menu_choices WHERE department_id=:department_id AND year=:year AND week=:week"), {"department_id": DEPT_ID, "year": YEAR, "week": 41})
        db.execute(text("DELETE FROM department_menu_choices WHERE department_id=:department_id AND year=:year AND week=:week"), {"department_id": DEPT_ID, "year": YEAR, "week": 42})
        db.commit()
    finally:
        db.close()

    seed_portal_menu_choice(tenant_id=1, site_id=SITE_ID, department_id=DEPT_ID, year=YEAR, week=YEAR, weekday=1, selected_variant="Alt1")


def test_department_portal_home_renders_identity_context_and_weeks(client_admin, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK, note="Privat notering")
    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO residences(id, site_id, name) VALUES('res-home', :site_id, 'Solgläntans äldreboende')"), {"site_id": SITE_ID})
        db.execute(text("UPDATE departments SET residence_id='res-home' WHERE id=:department_id"), {"department_id": DEPT_ID})
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES('portal-home-other', :site_id, 'Avd 2', 'manual')"), {"site_id": SITE_ID})
        db.commit()
    finally:
        db.close()
    _seed_requirement_group(SITE_ID, DEPT_ID)
    _seed_service_addon(SITE_ID, DEPT_ID)
    ResidentsWeeklyRepo().upsert_for_week(DEPT_ID, YEAR, WEEK, 18, 18)

    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=39)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=40)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=41)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=42)

    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO department_menu_choices(tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES (1, :site_id, :department_id, :year, 40, 1, 'lunch', 'alt1', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"site_id": SITE_ID, "department_id": DEPT_ID, "year": YEAR})
        db.execute(text("INSERT OR REPLACE INTO department_menu_choices(tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES (1, :site_id, :department_id, :year, 41, 1, 'lunch', 'alt1', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"site_id": SITE_ID, "department_id": DEPT_ID, "year": YEAR})
        db.commit()
    finally:
        db.close()

    submit_resp = client_admin.post(
        "/portal/department/week/submit",
        json={"year": YEAR, "week": 40},
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert submit_resp.status_code == 200

    resp = client_admin.get("/ui/portal/department", headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Avd 1" in html
    assert "Solgläntans äldreboende · 18 boende" in html
    assert "Avd 2" not in html
    assert "Privat notering" not in html
    assert html.count("18 boende") == 1
    assert "Timbal" in html
    assert "Glutenfri" in html
    assert "Sallad" in html
    assert "aldrig tomat" in html
    assert "Vecka 39" not in html
    assert "Vecka 40" in html
    assert "Vecka 41" in html
    assert "Vecka 42" in html
    assert "Färdig" in html
    assert "Påbörjad" in html
    assert "Ej påbörjad" in html
    assert "/ui/portal/department/week?year=2026&amp;week=40" in html
    assert "/ui/portal/department/week?year=2026&amp;week=41" in html
    assert "/ui/portal/department/week?year=2026&amp;week=42" in html
    assert "Request ID:" not in html
    assert 'data-theme-toggle' in html
    assert 'class="app-shell__sidebar"' not in html
    assert 'app-shell__body--no-sidebar' in html


def test_department_portal_home_unit_portal_uses_clean_url(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK)
    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO users(id, tenant_id, username, email, password_hash, role, full_name, is_active, department_id) VALUES(1, 1, 'unit', 'unit@example.com', 'hash', 'unit_portal', 'Unit User', 1, :department_id)"), {"department_id": DEPT_ID})
        db.execute(text("INSERT OR REPLACE INTO residences(id, site_id, name) VALUES('res-home', :site_id, 'Solgläntans äldreboende')"), {"site_id": SITE_ID})
        db.execute(text("UPDATE departments SET residence_id='res-home' WHERE id=:department_id"), {"department_id": DEPT_ID})
        db.commit()
    finally:
        db.close()

    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=40)

    resp = client_admin.get(
        "/ui/portal/department",
        headers={"X-User-Role": "unit_portal", "X-Tenant-Id": "1", "X-User-Id": "1"},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '/ui/portal/department?department_id=' not in html
    assert 'data-theme-toggle' in html
    assert 'class="app-shell__sidebar"' not in html
    assert 'app-shell__body--no-sidebar' in html


def test_department_portal_home_admin_explicit_department_context_still_works(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK)
    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO users(id, tenant_id, username, email, password_hash, role, full_name, is_active, department_id) VALUES(1, 1, 'admin', 'admin@example.com', 'hash', 'admin', 'Admin User', 1, NULL)"))
        db.execute(text("INSERT OR REPLACE INTO residences(id, site_id, name) VALUES('res-home', :site_id, 'Solgläntans äldreboende')"), {"site_id": SITE_ID})
        db.execute(text("UPDATE departments SET residence_id='res-home' WHERE id=:department_id"), {"department_id": DEPT_ID})
        db.commit()
    finally:
        db.close()

    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=40)

    resp = client_admin.get(
        f"/ui/portal/department?department_id={DEPT_ID}",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1", "X-User-Id": "1"},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Avd 1" in html
    assert "Solgläntans äldreboende" in html
    assert 'data-theme-toggle' in html
    assert 'class="app-shell__sidebar"' not in html


def test_department_portal_home_unit_portal_query_param_cannot_switch_department(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK)
    other_dept_id = "portal-home-other-dept"
    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:id, :site_id, 'Avd 2', 'manual')"), {"id": other_dept_id, "site_id": SITE_ID})
        db.execute(text("INSERT OR REPLACE INTO users(id, tenant_id, username, email, password_hash, role, full_name, is_active, department_id) VALUES(1, 1, 'unit', 'unit@example.com', 'hash', 'unit_portal', 'Unit User', 1, :department_id)"), {"department_id": DEPT_ID})
        db.commit()
    finally:
        db.close()

    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=40)

    resp = client_admin.get(
        f"/ui/portal/department?department_id={other_dept_id}",
        headers={"X-User-Role": "unit_portal", "X-Tenant-Id": "1", "X-User-Id": "1"},
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Avd 1" in html
    assert "Avd 2" not in html


def test_department_portal_home_hides_stale_complete_and_excludes_past_publications(client_admin, seed_portal_department_data, seed_canonical_builder_publication, seed_portal_menu_choice):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=39)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=40)

    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO department_menu_choices(tenant_id, site_id, department_id, year, week, weekday, meal, selected_variant, version, created_at, updated_at) VALUES (1, :site_id, :department_id, :year, 40, 1, 'lunch', 'alt1', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"site_id": SITE_ID, "department_id": DEPT_ID, "year": YEAR})
        db.commit()
    finally:
        db.close()

    submit_resp = client_admin.post(
        "/portal/department/week/submit",
        json={"year": YEAR, "week": 40},
        headers=_h(),
        environ_overrides={"test_claims": {"department_id": DEPT_ID}},
    )
    assert submit_resp.status_code == 200

    db = get_session()
    try:
        db.execute(text("UPDATE commun_builder_publication_pins SET builder_menu_version=2 WHERE tenant_id=1 AND site_id=:site_id AND year=:year AND week=40"), {"site_id": SITE_ID, "year": YEAR})
        db.commit()
    finally:
        db.close()

    resp = client_admin.get("/ui/portal/department", headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Vecka 39" not in html
    assert "Behöver granskas igen" in html
    assert "Färdig" not in html


def test_department_portal_home_shows_empty_state_without_publications(client_admin, seed_portal_department_data):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK)
    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO residences(id, site_id, name) VALUES('res-home', :site_id, 'Solgläntans äldreboende')"), {"site_id": SITE_ID})
        db.execute(text("UPDATE departments SET residence_id='res-home' WHERE id=:department_id"), {"department_id": DEPT_ID})
        db.execute(text("DELETE FROM commun_builder_publication_pins WHERE site_id=:site_id"), {"site_id": SITE_ID})
        db.commit()
    finally:
        db.close()

    resp = client_admin.get("/ui/portal/department", headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Inga menyer har publicerats ännu." in html
    assert "Vecka 40" not in html


def test_department_portal_home_normalizes_duplicate_requirement_labels(client_admin, seed_portal_department_data, seed_canonical_builder_publication):
    seed_portal_department_data(dept_id=DEPT_ID, site_id=SITE_ID, year=YEAR, week=WEEK)
    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO residences(id, site_id, name) VALUES('res-home', :site_id, 'Solgläntans äldreboende')"), {"site_id": SITE_ID})
        db.execute(text("UPDATE departments SET residence_id='res-home' WHERE id=:department_id"), {"department_id": DEPT_ID})
        db.commit()
    finally:
        db.close()

    _seed_duplicate_requirement_label_group(SITE_ID, DEPT_ID)
    _seed_publication(seed_canonical_builder_publication, site_id=SITE_ID, year=YEAR, week=40)

    resp = client_admin.get("/ui/portal/department", headers=_h(), environ_overrides={"test_claims": {"department_id": DEPT_ID}})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Glutenfri · Glutenfri" not in html
    assert "Glutenfri" in html
