from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient
import pytest
from core.department_menu_choice_repo import MenuChoiceRepo

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def app_with_alt2(app_session: Flask) -> Flask:
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        # seed
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-alt2-1','Alt2 Site')"))
        db.execute(text("""
            INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version)
            VALUES ('dept-alt2-1','site-alt2-1','Alt2 Dept','fixed', 5, NULL, 0)
        """))
        # Week 1 2024: enable Monday (1)
        db.execute(text(
            "INSERT OR REPLACE INTO weekview_alt2_flags (site_id, department_id, year, week, day_of_week, enabled) VALUES (:s,:d,:y,:w,:dow,1)"
        ), {"s": "site-alt2-1", "d": "dept-alt2-1", "y": 2024, "w": 1, "dow": 1})
        db.commit()
    finally:
        db.close()
    return app_session


def test_admin_department_alt2_get_returns_days(app_with_alt2: Flask, client_admin: FlaskClient) -> None:
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-alt2-1"
    repo = MenuChoiceRepo()
    repo.set_choice(
        tenant_id=1,
        site_id="site-alt2-1",
        department_id="dept-alt2-1",
        year=2024,
        week=1,
        weekday=1,
        selected_alt="Alt2",
    )
    repo.set_choice(
        tenant_id=1,
        site_id="site-alt2-1",
        department_id="dept-alt2-1",
        year=2024,
        week=1,
        weekday=2,
        selected_alt="Alt1",
    )
    from core.db import get_session
    from sqlalchemy import text
    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled) VALUES ('site-alt2-1','dept-alt2-1',2024,1,1,0)"))
        db.execute(text("INSERT OR REPLACE INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled) VALUES ('site-alt2-1','dept-alt2-1',2024,1,2,1)"))
        db.commit()
    finally:
        db.close()
    r = client_admin.get("/ui/admin/departments/dept-alt2-1/alt2?year=2024&week=1", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert data.get("department_id") == "dept-alt2-1"
    assert data.get("year") == 2024
    assert data.get("week") == 1
    assert data.get("choices", {}).get("mon") == "Alt2"
    assert data.get("choices", {}).get("tue") == "Alt1"
    assert data.get("choices", {}).get("wed") is None
    assert "mon" in (data.get("alt2_days") or [])
    assert "tue" not in (data.get("alt2_days") or [])


def test_admin_department_alt2_get_cross_site_forbidden(app_session: Flask, client_admin: FlaskClient) -> None:
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-a','Site A')"))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-b','Site B')"))
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES ('dept-a','site-a','Dept A','fixed', 10, NULL, 0)"))
        db.commit()
    finally:
        db.close()

    # Set active site to B (admin on site B)
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-b"

    # Attempt to fetch dept-a (belongs to site-a) should be forbidden
    r = client_admin.get("/ui/admin/departments/dept-a/alt2?year=2024&week=1", headers=ADMIN_HEADERS)
    assert r.status_code == 403


def test_admin_department_alt2_get_cross_tenant_forbidden(app_session: Flask, client_admin: FlaskClient) -> None:
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id) VALUES ('tenant-one-site','Tenant One Site', 1)"))
        db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id) VALUES ('tenant-two-site','Tenant Two Site', 2)"))
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES ('tenant-two-dept','tenant-two-site','Tenant Two Dept','fixed', 8, NULL, 0)"))
        db.commit()
    finally:
        db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = "tenant-one-site"
        sess["tenant_id"] = 1

    r = client_admin.get(
        "/ui/admin/departments/tenant-two-dept/alt2?year=2024&week=1&site_id=tenant-two-site",
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 403


def test_admin_department_alt2_get_missing_canonical_rows_returns_empty(app_session: Flask, client_admin: FlaskClient) -> None:
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id) VALUES ('site-missing-alt2','Missing Alt2 Site', 1)"))
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES ('dept-missing-alt2','site-missing-alt2','Dept Missing Alt2','fixed', 4, NULL, 0)"))
        db.commit()
    finally:
        db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-missing-alt2"

    r = client_admin.get(
        "/ui/admin/departments/dept-missing-alt2/alt2?year=2026&week=12",
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("department_id") == "dept-missing-alt2"
    assert data.get("year") == 2026
    assert data.get("week") == 12
    assert data.get("alt2_days") == []
    assert all(v is None for v in (data.get("choices") or {}).values())


def test_admin_department_alt2_get_allows_explicit_site_when_session_site_differs(app_with_alt2: Flask, client_admin: FlaskClient) -> None:
    # Simulate stale tab/session drift: active site differs from department site.
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "other-site"
    repo = MenuChoiceRepo()
    repo.set_choice(
        tenant_id=1,
        site_id="site-alt2-1",
        department_id="dept-alt2-1",
        year=2024,
        week=1,
        weekday=1,
        selected_alt="Alt2",
    )

    r = client_admin.get(
        "/ui/admin/departments/dept-alt2-1/alt2?year=2024&week=1&site_id=site-alt2-1",
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("department_id") == "dept-alt2-1"
    assert "mon" in (data.get("alt2_days") or [])
    assert data.get("choices", {}).get("mon") == "Alt2"


def test_admin_department_alt2_get_canonical_wins_over_legacy_flags(app_session: Flask, client_admin: FlaskClient) -> None:
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id) VALUES ('site-legacy-alt2','Legacy Alt2 Site', 1)"))
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES ('dept-legacy-alt2','site-legacy-alt2','Dept Legacy Alt2','fixed', 4, NULL, 0)"))
        db.execute(text(
            """
            INSERT OR REPLACE INTO weekview_alt2_flags(site_id, department_id, year, week, day_of_week, enabled)
            VALUES ('site-legacy-alt2', 'dept-legacy-alt2', 2026, 12, 1, 1)
            """
        ))
        db.commit()
    finally:
        db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-legacy-alt2"

    r = client_admin.get(
        "/ui/admin/departments/dept-legacy-alt2/alt2?year=2026&week=12",
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("choices", {}).get("mon") is None
    assert "mon" not in (data.get("alt2_days") or [])
