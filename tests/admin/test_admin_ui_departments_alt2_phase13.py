from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient
import pytest

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.fixture
def app_with_alt2(app_session: Flask) -> Flask:
    from core.db import get_session
    from sqlalchemy import text

    db = get_session()
    try:
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS sites (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL
            )
            """
        ))
        db.execute(text(
            """
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
            """
        ))
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
              site_id TEXT NOT NULL,
              department_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              day_of_week INTEGER NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 0,
              UNIQUE(site_id, department_id, year, week, day_of_week)
            )
            """
        ))
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
    r = client_admin.get("/ui/admin/departments/dept-alt2-1/alt2?year=2024&week=1", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert data.get("department_id") == "dept-alt2-1"
    assert data.get("year") == 2024
    assert data.get("week") == 1
    # Monday should be enabled
    assert "mon" in (data.get("alt2_days") or [])


def test_admin_department_alt2_get_cross_site_forbidden(app_session: Flask, client_admin: FlaskClient) -> None:
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
        # Two sites and one department on site A
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-a','Site A')"))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-b','Site B')"))
        db.execute(text("""
            INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version)
            VALUES ('dept-a','site-a','Dept A','fixed', 10, NULL, 0)
        """))
        db.commit()
    finally:
        db.close()

    # Set active site to B (admin on site B)
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-b"

    # Attempt to fetch dept-a (belongs to site-a) should be forbidden
    r = client_admin.get("/ui/admin/departments/dept-a/alt2?year=2024&week=1", headers=ADMIN_HEADERS)
    assert r.status_code == 403
