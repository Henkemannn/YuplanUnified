from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient
import pytest

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

@pytest.fixture
def app_with_dept(app_session: Flask) -> Flask:
    from core.db import get_session
    from sqlalchemy import text
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


def test_admin_department_alt2_post_cross_site_forbidden(app_with_dept: Flask, client_admin: FlaskClient) -> None:
    # Active site is different
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "other-site"
    r = client_admin.post("/ui/admin/departments/dept-sv-1/alt2", json={"year": 2026, "week": 4, "alt2_days": ["mon"]}, headers=ADMIN_HEADERS)
    assert r.status_code == 403
