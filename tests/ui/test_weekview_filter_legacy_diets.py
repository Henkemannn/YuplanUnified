from __future__ import annotations

import uuid
from datetime import date as _date

import pytest


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers=_h("admin"),
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_weekview")
def test_weekview_hides_legacy_diet_labels(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())

    today_iso = _date.today().isocalendar()
    year, week = int(today_iso[0]), int(today_iso[1])

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.admin_repo import DepartmentsRepo

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0) ON CONFLICT(id) DO NOTHING"),
                {"i": site_id, "n": "Legacy Filter Site"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"
                ),
                {"i": dep_id, "s": site_id, "n": "Avd Filter"},
            )
            db.commit()

            # Seed defaults with labels "1", "Legacy 1" and a legitimate one "Gluten"
            # Counts arbitrary >0 so they render if not filtered
            DepartmentsRepo().upsert_department_diet_defaults(
                dep_id,
                expected_version=0,
                items=[
                    {"diet_type_id": "1", "default_count": 1},
                    {"diet_type_id": "Legacy 1", "default_count": 1},
                    {"diet_type_id": "Gluten", "default_count": 2},
                ],
            )
        finally:
            db.close()

    # Align session site context
    client_admin.post(
        "/ui/select-site",
        data={"site_id": site_id, "next": "/"},
        headers=_h("admin"),
    )

    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)

    # Assert only the valid label remains visible
    assert "Gluten [2]" in html

    # Ensure legacy/sentinel labels are not rendered as diet pills
    assert "data-diet-type-id=\"1\"" not in html
    assert "data-diet-type-id=\"Legacy 1\"" not in html
    assert "Legacy 1 [1]" not in html
    # "1" can occur widely; check the pill-specific pattern instead
    assert " 1 [1]" not in html and "] 1 [1]" not in html
