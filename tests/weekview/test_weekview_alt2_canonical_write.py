from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200


def _create_site_and_department(app_session, *, site_name: str, department_name: str) -> tuple[str, str]:
    from core.admin_repo import DepartmentsRepo, SitesRepo

    with app_session.app_context():
        site, _ = SitesRepo().create_site(site_name)
        department, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name=department_name,
            resident_count_mode="fixed",
            resident_count_fixed=10,
        )
    return str(site["id"]), str(department["id"])


def _seed_weekly_alt2_state(site_id: str, department_id: str, year: int, week: int) -> None:
    from core.department_menu_choice_repo import MenuChoiceRepo

    repo = MenuChoiceRepo()
    repo.set_choice(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week, weekday=1, selected_alt="Alt1", meal="lunch")
    repo.set_choice(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week, weekday=2, selected_alt="Alt2", meal="lunch")
    repo.set_choice(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week, weekday=5, selected_alt="Alt2", meal="lunch")


def test_replace_alt2_days_preserves_explicit_alt1_and_clears_removed_alt2(app_session):
    from core.department_menu_choice_repo import MenuChoiceRepo

    site_id, department_id = _create_site_and_department(app_session, site_name="Alt2 Preserve Site", department_name="Alt2 Preserve Dept")
    year, week = 2026, 6

    with app_session.app_context():
        repo = MenuChoiceRepo()
        _seed_weekly_alt2_state(site_id, department_id, year, week)
        repo.replace_alt2_days(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week, days=[5], meal="lunch")
        derived = repo.derive_map(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week)

    assert derived["mon"] == "Alt1"
    assert derived["tue"] is None
    assert derived["fri"] == "Alt2"


def test_replace_alt2_days_empty_clears_only_alt2_rows(app_session):
    from core.department_menu_choice_repo import MenuChoiceRepo

    site_id, department_id = _create_site_and_department(app_session, site_name="Alt2 Clear Site", department_name="Alt2 Clear Dept")
    year, week = 2026, 7

    with app_session.app_context():
        repo = MenuChoiceRepo()
        _seed_weekly_alt2_state(site_id, department_id, year, week)
        repo.replace_alt2_days(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week, days=[], meal="lunch")
        derived = repo.derive_map(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week)

    assert derived["mon"] == "Alt1"
    assert derived["tue"] is None
    assert derived["fri"] is None


def test_replace_alt2_days_public_api_commits_standalone(app_session):
    from core.db import get_session
    from core.department_menu_choice_repo import MenuChoiceRepo

    site_id, department_id = _create_site_and_department(app_session, site_name="Alt2 Commit Site", department_name="Alt2 Commit Dept")
    year, week = 2026, 10

    with app_session.app_context():
        MenuChoiceRepo().replace_alt2_days(
            tenant_id=1,
            site_id=site_id,
            department_id=department_id,
            year=year,
            week=week,
            days=[2, 5],
            meal="lunch",
        )

    db = get_session()
    try:
        rows = db.execute(
            text(
                "SELECT weekday, selected_variant FROM department_menu_choices WHERE tenant_id=1 AND site_id=:site_id AND department_id=:dep AND year=:year AND week=:week ORDER BY weekday"
            ),
            {"site_id": site_id, "dep": department_id, "year": year, "week": week},
        ).fetchall()
    finally:
        db.close()

    assert [(int(row[0]), str(row[1])) for row in rows] == [(2, "alt2"), (5, "alt2")]


def test_weekview_alt2_mirror_matches_requested_days(app_session):
    from core.db import get_session
    from core.weekview.repo import WeekviewRepo

    site_id, department_id = _create_site_and_department(app_session, site_name="Alt2 Mirror Site", department_name="Alt2 Mirror Dept")
    year, week = 2026, 8

    with app_session.app_context():
        WeekviewRepo().set_alt2_flags(tenant_id=1, year=year, week=week, department_id=department_id, days=[2, 5], site_id=site_id)
        db = get_session()
        try:
            canonical = db.execute(
                text(
                    "SELECT weekday, selected_variant FROM department_menu_choices WHERE tenant_id=1 AND site_id=:site_id AND department_id=:dep AND year=:year AND week=:week ORDER BY weekday"
                ),
                {"site_id": site_id, "dep": department_id, "year": year, "week": week},
            ).fetchall()
            legacy = db.execute(
                text(
                    "SELECT day_of_week FROM weekview_alt2_flags WHERE site_id=:site_id AND department_id=:dep AND year=:year AND week=:week ORDER BY day_of_week"
                ),
                {"site_id": site_id, "dep": department_id, "year": year, "week": week},
            ).fetchall()
        finally:
            db.close()

    assert [(int(row[0]), str(row[1])) for row in canonical] == [(2, "alt2"), (5, "alt2")]
    assert [int(row[0]) for row in legacy] == [2, 5]


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_alt2_patch_roundtrip_updates_canonical_read(client_admin):
    from core.admin_repo import DepartmentsRepo, SitesRepo
    from core.department_menu_choice_repo import MenuChoiceRepo

    app = client_admin.application
    year, week = 2026, 9

    with app.app_context():
        site, _ = SitesRepo().create_site("Alt2 API Site")
        department, _ = DepartmentsRepo().create_department(site_id=site["id"], name="Alt2 API Dept", resident_count_mode="fixed", resident_count_fixed=10)

    site_id = str(site["id"])
    department_id = str(department["id"])

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    base = f"/api/weekview?year={year}&week={week}&department_id={department_id}"
    etag0 = client_admin.get(base, headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"}).headers.get("ETag")
    patch = client_admin.patch(
        "/api/weekview/alt2",
        json={"tenant_id": 1, "site_id": site_id, "department_id": department_id, "year": year, "week": week, "days": [2, 5]},
        headers={"X-User-Role": "editor", "X-Tenant-Id": "1", "If-Match": etag0},
    )
    assert patch.status_code == 200
    etag1 = patch.headers.get("ETag")
    assert etag1 and etag1 != etag0

    data = client_admin.get(base, headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"}).get_json()
    alt2_days = data["department_summaries"][0].get("alt2_days", [])
    assert sorted(alt2_days) == [2, 5]

    derived = MenuChoiceRepo().derive_map(tenant_id=1, site_id=site_id, department_id=department_id, year=year, week=week)
    assert derived["tue"] == "Alt2"
    assert derived["fri"] == "Alt2"
