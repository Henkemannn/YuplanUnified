from __future__ import annotations

import re
from datetime import date
from flask import Flask
from flask.testing import FlaskClient

from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo, DietDefaultsRepo
from core.residents_weekly_repo import ResidentsWeeklyRepo

HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _iso_week():
    iso = date.today().isocalendar()
    return iso[0], iso[1]


def _seed_basic():
    site, _ = SitesRepo().create_site("Test Site")
    return site


def test_get_department_detail_page(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    # Activate this site for the session
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Alfa", resident_count_mode="fixed", resident_count_fixed=10
    )
    # add notes manually (if column exists)
    from core.db import get_session
    from sqlalchemy import text
    db = get_session()
    try:
        cols = {r[1] for r in db.execute(text("PRAGMA table_info('departments')")).fetchall()}
        if "notes" in cols:
            db.execute(text("UPDATE departments SET notes='Testinfo om avdelningen' WHERE id=:id"), {"id": dept["id"]})
            db.commit()
    finally:
        db.close()

    r = client_admin.get(f"/ui/admin/departments/{dept['id']}/detail", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.data.decode()
    assert "Avdelning" in html and "Avd Alfa" in html
    assert "admin-detail-site-chip" in html
    assert "Test Site" in html
    assert '<div class="app-shell__card-meta">Vecka ' not in html
    assert "Boendeantal" in html
    assert "Testinfo om avdelningen" in html
    assert "Redigera" in html
    assert f"/ui/admin/departments/{dept['id']}/edit" in html
    assert "content-header" not in html
    assert "site_id:" not in html
    assert "<input" not in html


def test_post_updates_fixed_resident_count(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Fix", resident_count_mode="fixed", resident_count_fixed=8
    )
    # POST to update fixed value
    r = client_admin.post(
        f"/ui/admin/departments/{dept['id']}/detail/fixed",
        headers=HEADERS_ADMIN,
        data={"resident_count_fixed": "12"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    # GET detail and verify value in page
    r2 = client_admin.get(f"/ui/admin/departments/{dept['id']}/detail", headers=HEADERS_ADMIN)
    html2 = r2.data.decode()
    assert "Normalt antal:" in html2
    assert "12" in html2


def test_post_creates_weekly_override_and_reflects(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Weekly", resident_count_mode="fixed", resident_count_fixed=10
    )
    year, week = _iso_week()
    form = {f"dept_{dept['id']}_lunch": "7", f"dept_{dept['id']}_dinner": "12", "year": str(year), "week": str(week)}
    r = client_admin.post(
        f"/ui/admin/departments/{dept['id']}/detail",
        headers=HEADERS_ADMIN,
        data=form,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    # GET detail should show override values
    r2 = client_admin.get(f"/ui/admin/departments/{dept['id']}/detail", headers=HEADERS_ADMIN)
    html2 = r2.data.decode()
    assert "Veckoöverstyrning" in html2
    assert ">7<" in html2
    assert ">12<" in html2


def test_post_clears_weekly_override(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Reset", resident_count_mode="fixed", resident_count_fixed=10
    )
    year, week = _iso_week()
    # Seed override directly
    ResidentsWeeklyRepo().upsert_for_week(dept["id"], year, week, residents_lunch=7, residents_dinner=12)

    # Clear by posting empty values
    form = {f"dept_{dept['id']}_lunch": "", f"dept_{dept['id']}_dinner": "", "year": str(year), "week": str(week)}
    r = client_admin.post(
        f"/ui/admin/departments/{dept['id']}/detail",
        headers=HEADERS_ADMIN,
        data=form,
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    # Should fall back to fixed 10 now
    r2 = client_admin.get(f"/ui/admin/departments/{dept['id']}/detail", headers=HEADERS_ADMIN)
    html2 = r2.data.decode()
    assert "Inga veckovariationer sparade för vald vecka." in html2
    assert "Normalt antal:" in html2
    assert "10 boende" in html2


def test_departments_list_shows_link_and_varierat_badge(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    # Create a department with notes
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Beta", resident_count_mode="fixed", resident_count_fixed=11
    )
    # Add notes
    from core.db import get_session
    from sqlalchemy import text
    db = get_session()
    try:
        db.execute(text("UPDATE departments SET notes='Viktig info' WHERE id=:id"), {"id": dept["id"]})
        db.commit()
    finally:
        db.close()

    # Seed weekly override for badge visibility
    year, week = _iso_week()
    ResidentsWeeklyRepo().upsert_for_week(dept["id"], year, week, residents_lunch=5, residents_dinner=None)

    r = client_admin.get("/ui/admin/departments", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.data.decode()
    # Link to detail page
    assert f"/ui/admin/departments/{dept['id']}/detail" in html
    # Notes are visible
    assert "Viktig info" in html
    # Varierat badge present
    assert "Varierat" in html


def test_department_detail_is_read_only_dashboard(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Readonly", resident_count_mode="fixed", resident_count_fixed=9
    )
    r = client_admin.get(f"/ui/admin/departments/{dept['id']}/detail", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.data.decode()
    assert f"/ui/admin/departments/{dept['id']}/edit" in html
    assert "Grundinformation" in html
    assert "Specialkost" in html
    assert "Snabbstatistik" in html
    assert "<input" not in html
    assert "Spara" not in html


def test_department_detail_specialkost_list_and_total_sum(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Diet", resident_count_mode="fixed", resident_count_fixed=9
    )
    diet_repo = DietTypesRepo()
    dt_laktos = diet_repo.create(site_id=site["id"], name="Laktos", default_select=False)
    dt_gluten = diet_repo.create(site_id=site["id"], name="Gluten", default_select=False)
    dt_veg = diet_repo.create(site_id=site["id"], name="Vegan", default_select=False)
    version = DepartmentsRepo().get_version(dept["id"]) or 0
    DepartmentsRepo().upsert_department_diet_defaults(
        dept["id"],
        version,
        [
            {"diet_type_id": str(dt_laktos), "default_count": 1},
            {"diet_type_id": str(dt_gluten), "default_count": 2},
            {"diet_type_id": str(dt_veg), "default_count": 0},
        ],
    )
    year, week = _iso_week()
    ResidentsWeeklyRepo().upsert_for_week(dept["id"], year, week, residents_lunch=9, residents_dinner=9)
    r = client_admin.get(f"/ui/admin/departments/{dept['id']}/detail", headers=HEADERS_ADMIN)
    assert r.status_code == 200
    html = r.data.decode()
    assert "admin-detail-site-chip" in html
    assert "Test Site" in html
    assert '<div class="app-shell__card-meta">Vecka ' not in html
    assert "Gluten" in html
    assert "Laktos" in html
    assert "Vegan" not in html
    assert "sk-pill" in html
    assert "Totalt:</strong> 3 personer" in html
    assert "Totalt antal specialkost:" in html
    assert "Totalt antal specialkost:</strong> 3" in html
    assert "Totalt standardantal specialkost:" not in html
    assert "Ingen specialkost registrerad." not in html
    assert "<input" not in html


def test_edit_single_submit_saves_name_and_specialkost_then_shows_on_detail(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site["id"]
    dept, _ = DepartmentsRepo().create_department(
        site_id=site["id"], name="Avd Single Save", resident_count_mode="fixed", resident_count_fixed=11
    )
    diet_id = DietTypesRepo().create(site_id=site["id"], name="Laktos", default_select=False)
    version = DepartmentsRepo().get_version(dept["id"]) or 0

    resp = client_admin.post(
        f"/ui/admin/departments/{dept['id']}/edit",
        headers=HEADERS_ADMIN,
        data={
            "name": "Avd Single Save Uppdaterad",
            "resident_count": "11",
            "notes": "",
            "version": str(version),
            f"diet_default_{diet_id}": "4",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    defaults = DietDefaultsRepo().list_for_department(dept["id"])
    found = {int(it["diet_type_id"]): int(it.get("default_count", 0) or 0) for it in defaults}
    assert found.get(int(diet_id)) == 4

    detail = client_admin.get(f"/ui/admin/departments/{dept['id']}/detail", headers=HEADERS_ADMIN)
    assert detail.status_code == 200
    detail_html = detail.data.decode()
    assert "Avd Single Save Uppdaterad" in detail_html
    assert "Laktos" in detail_html
    assert "4 personer" in detail_html
