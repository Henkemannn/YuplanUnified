from __future__ import annotations

import re
from datetime import date
from flask import Flask
from flask.testing import FlaskClient

from core.admin_repo import SitesRepo, DepartmentsRepo
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
    assert "Antal boende" in html  # label present
    assert "Testinfo om avdelningen" in html


def test_post_updates_fixed_resident_count(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
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
    assert 'name="resident_count_fixed"' in html2 or "Antal boende" in html2
    assert "12" in html2


def test_post_creates_weekly_override_and_reflects(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
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
    assert f'name="dept_{dept["id"]}_lunch" value="7"' in html2
    assert f'name="dept_{dept["id"]}_dinner" value="12"' in html2
    # Optional: page may or may not display a specific "Varierat" text; skip strict assert here


def test_post_clears_weekly_override(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
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
    assert f'name="dept_{dept["id"]}_lunch" value="10"' in html2
    assert f'name="dept_{dept["id"]}_dinner" value="10"' in html2


def test_departments_list_shows_link_and_varierat_badge(app_session: Flask, client_admin: FlaskClient) -> None:
    site = _seed_basic()
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
