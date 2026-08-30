from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient
import pytest
from core.department_menu_choice_repo import MenuChoiceRepo
from portal.department.auth import DepartmentPortalScope
from portal.department.service import build_department_week_payload

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

@pytest.fixture
def app_with_dept(app_session: Flask) -> Flask:
    from core.db import get_session
    from sqlalchemy import text
    db = get_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-sv-1','Site Save')"))
        db.execute(text("""
            INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version)
            VALUES ('dept-sv-1','site-sv-1','Dept Save','fixed', 12, NULL, 0)
        """))
        db.commit()
    finally:
        db.close()
    return app_session


def test_admin_department_alt2_post_and_get_roundtrip(app_with_dept: Flask, client_admin: FlaskClient) -> None:
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-sv-1"
    # Save mon+tue
    r1 = client_admin.post("/ui/admin/departments/dept-sv-1/alt2", json={"year": 2026, "week": 4, "alt2_days": ["mon","tue"]}, headers=ADMIN_HEADERS)
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1 and sorted(d1.get("alt2_days") or []) == ["mon","tue"]
    # GET mirrors saved days
    r2 = client_admin.get("/ui/admin/departments/dept-sv-1/alt2?year=2026&week=4", headers=ADMIN_HEADERS)
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2 and sorted(d2.get("alt2_days") or []) == ["mon","tue"]


def test_admin_department_alt2_post_choices_roundtrip_and_portal_reads_canonical(app_with_dept: Flask, client_admin: FlaskClient) -> None:
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-sv-1"
    r1 = client_admin.post(
        "/ui/admin/departments/dept-sv-1/alt2",
        json={
            "year": 2026,
            "week": 5,
            "choices": {
                "mon": "Alt2",
                "tue": "Alt1",
                "wed": None,
                "thu": None,
                "fri": None,
                "sat": None,
                "sun": None,
            },
        },
        headers=ADMIN_HEADERS,
    )
    assert r1.status_code == 200
    d1 = r1.get_json() or {}
    assert d1.get("choices", {}).get("mon") == "Alt2"
    assert d1.get("choices", {}).get("tue") == "Alt1"
    assert d1.get("choices", {}).get("wed") is None
    assert d1.get("alt2_days") == ["mon"]

    r2 = client_admin.get("/ui/admin/departments/dept-sv-1/alt2?year=2026&week=5", headers=ADMIN_HEADERS)
    assert r2.status_code == 200
    d2 = r2.get_json() or {}
    assert d2.get("choices", {}).get("mon") == "Alt2"
    assert d2.get("choices", {}).get("tue") == "Alt1"
    assert d2.get("choices", {}).get("wed") is None
    assert d2.get("alt2_days") == ["mon"]

    repo = MenuChoiceRepo()
    rows = repo.list_for_department_week(tenant_id=1, site_id="site-sv-1", department_id="dept-sv-1", year=2026, week=5)
    assert any(r.weekday == 1 and r.selected_variant == "alt2" for r in rows)
    assert any(r.weekday == 2 and r.selected_variant == "alt1" for r in rows)

    scope = DepartmentPortalScope(user_id=1, role="admin", tenant_id=1, department_id="dept-sv-1", site_id="site-sv-1")
    payload = build_department_week_payload(scope, 2026, 5)
    monday = next(d for d in payload["days"] if d["weekday_name"] == "Måndag")
    tuesday = next(d for d in payload["days"] if d["weekday_name"] == "Tisdag")
    assert monday["choice"]["selected_alt"] == "Alt2"
    assert tuesday["choice"]["selected_alt"] == "Alt1"


def test_admin_department_alt2_post_cross_site_forbidden(app_with_dept: Flask, client_admin: FlaskClient) -> None:
    # Active site is different
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-sv-other"
        sess["tenant_id"] = 1

    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id) VALUES ('site-sv-other','Site Save Other', 1)"))
        db.commit()
    finally:
        db.close()

    r = client_admin.post("/ui/admin/departments/dept-sv-1/alt2", json={"year": 2026, "week": 4, "alt2_days": ["mon"]}, headers=ADMIN_HEADERS)
    assert r.status_code == 403
