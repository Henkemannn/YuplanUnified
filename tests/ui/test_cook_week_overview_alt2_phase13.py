from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import text
import pytest

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

@pytest.fixture
def app_with_cook_data(app_session: Flask) -> Flask:
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS sites (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS departments (
              id TEXT PRIMARY KEY,
              site_id TEXT NOT NULL,
              name TEXT NOT NULL,
              resident_count_mode TEXT NOT NULL DEFAULT 'fixed',
              resident_count_fixed INTEGER NOT NULL DEFAULT 0,
              notes TEXT NULL,
              version INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
              site_id TEXT NOT NULL,
              department_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              day_of_week INTEGER NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 0,
              UNIQUE(site_id, department_id, year, week, day_of_week)
            )
        """))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-cook-1','Cook Site')"))
        db.execute(text("""
            INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version)
            VALUES ('dept-cook-1','site-cook-1','Cook Dept','fixed', 8, NULL, 0)
        """))
        db.commit()
    finally:
        db.close()
    return app_session


def test_cook_week_overview_alt2_flags_present(app_with_cook_data: Flask, client_admin: FlaskClient) -> None:
    # Save Alt2 for mon+tue via admin POST
    with client_admin.session_transaction() as s1:
        s1["site_id"] = "site-cook-1"
    r1 = client_admin.post("/ui/admin/departments/dept-cook-1/alt2", json={"year": 2026, "week": 4, "alt2_days": ["mon","tue"]}, headers=ADMIN_HEADERS)
    assert r1.status_code == 200
    # Verify weekview service reports alt2 days for the department
    from core.weekview.service import WeekviewService
    svc = WeekviewService()
    payload, _ = svc.fetch_weekview(tenant_id=1, year=2026, week=4, department_id="dept-cook-1", site_id="site-cook-1")
    summaries = payload.get("department_summaries") or []
    assert len(summaries) == 1
    alt2_days = set(summaries[0].get("alt2_days") or [])
    assert 1 in alt2_days and 2 in alt2_days
