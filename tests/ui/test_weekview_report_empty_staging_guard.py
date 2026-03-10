from __future__ import annotations

import uuid

from sqlalchemy import text

from core.db import create_all, get_session


def _h(role: str) -> dict:
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def _seed_site_and_department(app, site_id: str, dep_id: str) -> None:
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO sites(id, name, version) VALUES(:i,:n,0) "
                    "ON CONFLICT(id) DO NOTHING"
                ),
                {"i": site_id, "n": "Guard Site"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"
                ),
                {"i": dep_id, "s": site_id, "n": "Guard Dep"},
            )
            db.commit()
        finally:
            db.close()


def _force_legacy_alt2_schema(app) -> None:
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("DROP TABLE IF EXISTS weekview_alt2_flags"))
            db.execute(
                text(
                    """
                    CREATE TABLE weekview_alt2_flags (
                      tenant_id TEXT NOT NULL,
                      department_id TEXT NOT NULL,
                      year INTEGER NOT NULL,
                      week INTEGER NOT NULL,
                      day_of_week INTEGER NOT NULL,
                      is_alt2 INTEGER NOT NULL DEFAULT 0,
                      UNIQUE (tenant_id, department_id, year, week, day_of_week)
                    )
                    """
                )
            )
            db.commit()
        finally:
            db.close()


def test_weekview_ui_legacy_alt2_schema_does_not_500(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    _seed_site_and_department(app, site_id, dep_id)
    _force_legacy_alt2_schema(app)

    with client_admin.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id

    resp = client_admin.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year=2026&week=11",
        headers=_h("admin"),
    )
    assert resp.status_code == 200


def test_weekview_report_ui_legacy_alt2_schema_empty_dataset_does_not_500(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    _seed_site_and_department(app, site_id, dep_id)
    _force_legacy_alt2_schema(app)

    with client_admin.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id

    resp = client_admin.get(
        f"/ui/reports/weekview?site_id={site_id}&year=2026&week=11",
        headers=_h("admin"),
    )
    assert resp.status_code == 200


def test_reports_weekly_no_site_selected_redirects_not_500(client_admin):
    with client_admin.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess.pop("site_id", None)

    resp = client_admin.get(
        "/ui/reports/weekly?year=2026&week=11",
        headers=_h("superuser"),
        follow_redirects=False,
    )
    assert resp.status_code in (302, 400)
