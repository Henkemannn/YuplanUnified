from __future__ import annotations

from tests._auth_site_helpers import login_bound_user

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
def test_weekview_hides_legacy_diet_labels(client_admin, monkeypatch):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())

    today_iso = _date.today().isocalendar()
    year, week = int(today_iso[0]), int(today_iso[1])

    from core.db import create_all, get_session
    from sqlalchemy import text
    from core.admin_repo import DepartmentsRepo, DietTypesRepo

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text("INSERT INTO sites(id, name, tenant_id, version) VALUES(:i,:n,1,0) ON CONFLICT(id) DO NOTHING"),
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
        finally:
            db.close()

    diet_id = DietTypesRepo().create(
        site_id=site_id,
        tenant_id=1,
        name="Gluten",
        semantics="atomic",
    )
    DepartmentsRepo().upsert_department_diet_defaults(
        dep_id,
        expected_version=0,
        items=[{"diet_type_id": str(diet_id), "default_count": 2}],
    )
    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) "
                    "VALUES(:d,:legacy,:c),(:d,:orphan,:c)"
                ),
                {"d": dep_id, "legacy": "Legacy 1", "orphan": "999", "c": 1},
            )
            db.commit()
        finally:
            db.close()

    login_bound_user(client_admin, site_id=site_id)

    from core.weekview.schema import WeekviewSchemaError
    from core.weekview.service import WeekviewService

    validation_failures = []
    verify_diet_schema = WeekviewService._verify_diet_schema

    def capture_diet_validation(service, department_id):
        try:
            verify_diet_schema(service, department_id)
        except WeekviewSchemaError as exc:
            validation_failures.append((department_id, str(exc)))
            raise

    monkeypatch.setattr(WeekviewService, "_verify_diet_schema", capture_diet_validation)
    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 500
    assert validation_failures
    assert set(validation_failures) == {(dep_id, "Diet reference incompatible")}
    with app.app_context():
        db = get_session()
        try:
            corrupt_rows = db.execute(
                text(
                    "SELECT diet_type_id, default_count FROM department_diet_defaults "
                    "WHERE department_id=:department_id AND diet_type_id IN ('Legacy 1','999') "
                    "ORDER BY diet_type_id"
                ),
                {"department_id": dep_id},
            ).fetchall()
            assert [(str(row[0]), int(row[1])) for row in corrupt_rows] == [
                ("999", 1),
                ("Legacy 1", 1),
            ]
            db.execute(
                text(
                    "DELETE FROM department_diet_defaults "
                    "WHERE department_id=:department_id AND diet_type_id IN ('Legacy 1','999')"
                ),
                {"department_id": dep_id},
            )
            db.commit()
        finally:
            db.close()

    r_ui = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year={year}&week={week}",
        headers=_h("admin"),
    )
    assert r_ui.status_code == 200
    html = r_ui.get_data(as_text=True)

    # Assert only the valid label remains visible
    assert "Gluten [2]" in html

    # Ensure legacy/sentinel labels are not rendered as diet pills
    assert "Legacy 1 [1]" not in html
