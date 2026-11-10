from flask.testing import FlaskClient
import pytest
from core.app_factory import create_app
from core.db import get_session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def _seed(db):
    # Robust inserts compatible with existing dev.db schema (explicit NOT NULL columns)
    db.execute(text("INSERT OR REPLACE INTO sites(id, tenant_id, name, version) VALUES('s1',1,'Site 1',0)"))
    db.execute(text("INSERT OR REPLACE INTO sites(id, tenant_id, name, version) VALUES('s2',1,'Site 2',0)"))
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES('d1','s1','Dept 1','fixed',0,0)"))
    db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES('d2','s2','Dept 2','fixed',0,0)"))
    # Ensure weekview tables exist
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_versions (tenant_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 0, UNIQUE (tenant_id, department_id, year, week))"))
    db.execute(text("CREATE TABLE IF NOT EXISTS weekview_registrations (tenant_id TEXT NOT NULL, department_id TEXT NOT NULL, year INTEGER NOT NULL, week INTEGER NOT NULL, day_of_week INTEGER NOT NULL, meal TEXT NOT NULL, diet_type TEXT NOT NULL, marked INTEGER NOT NULL DEFAULT 0, UNIQUE (tenant_id, department_id, year, week, day_of_week, meal, diet_type))"))
    db.commit()


def test_toggle_mark_respects_active_site_and_persists():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed(db)
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    # Session: admin on s1
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = "s1"
    # Seed ETag version for dept d1
    db = get_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO weekview_versions(tenant_id,department_id,year,week,version) VALUES('1','d1',2025,10,0)"))
        db.commit()
    finally:
        db.close()
    # Fetch ETag
    r_etag = client.get("/api/weekview/etag?department_id=d1&year=2025&week=10")
    assert r_etag.status_code == 200
    etag = r_etag.get_json().get("etag")
    assert etag
    # Toggle mark for Monday lunch Gluten
    payload = {
        "year": 2025,
        "week": 10,
        "department_id": "d1",
        "meal": "Lunch",
        "weekday_abbr": "Mån",
        "diet_type_id": "Gluten",
        "marked": True,
    }
    r_mark = client.post("/api/weekview/specialdiets/mark", json=payload, headers={"If-Match": etag, "X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r_mark.status_code == 200
    j = r_mark.get_json()
    assert j and j.get("status") == "ok" and j.get("marked") is True
    # Verify row persisted
    db = get_session()
    try:
        row = db.execute(text("SELECT marked FROM weekview_registrations WHERE tenant_id='1' AND department_id='d1' AND year=2025 AND week=10 AND day_of_week=1 AND meal='lunch' AND diet_type='Gluten'"))
        rec = row.fetchone()
        assert rec and int(rec[0]) == 1
    finally:
        db.close()


def test_toggle_mark_blocked_when_wrong_site():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed(db)
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    # Session: admin on s1, but toggling d2 which is s2
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = "s1"
    # ETag for d2
    db = get_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO weekview_versions(tenant_id,department_id,year,week,version) VALUES('1','d2',2025,10,0)"))
        db.commit()
    finally:
        db.close()
    r_etag = client.get("/api/weekview/etag?department_id=d2&year=2025&week=10")
    assert r_etag.status_code == 200
    etag = r_etag.get_json().get("etag")
    assert etag
    payload = {
        "year": 2025,
        "week": 10,
        "department_id": "d2",
        "meal": "Lunch",
        "weekday_abbr": "Mån",
        "diet_type_id": "Gluten",
        "marked": True,
    }
    r_mark = client.post("/api/weekview/specialdiets/mark", json=payload, headers={"If-Match": etag, "X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r_mark.status_code == 403


def test_toggle_mark_rejects_scope_database_failure(monkeypatch):
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed(db)
            db.execute(
                text(
                    "INSERT OR IGNORE INTO weekview_versions"
                    "(tenant_id,department_id,year,week,version) "
                    "VALUES('1','d1',2025,10,0)"
                )
            )
            db.commit()
        finally:
            db.close()

    client: FlaskClient = app.test_client()
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = "s1"

    etag = client.get(
        "/api/weekview/etag?department_id=d1&year=2025&week=10"
    ).get_json()["etag"]

    def fail_scope_lookup():
        raise SQLAlchemyError("simulated scope lookup failure")

    monkeypatch.setattr("core.ui_blueprint.get_session", fail_scope_lookup)
    response = client.post(
        "/api/weekview/specialdiets/mark",
        json={
            "year": 2025,
            "week": 10,
            "department_id": "d1",
            "meal": "Lunch",
            "weekday_abbr": "Mån",
            "diet_type_id": "Gluten",
            "marked": True,
        },
        headers={"If-Match": etag, "X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 500
    assert response.get_json()["title"] == "server_error"


def test_toggle_mark_rejects_site_owned_by_another_tenant():
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            _seed(db)
            db.execute(text("UPDATE sites SET tenant_id=2 WHERE id='s2'"))
            db.execute(
                text(
                    "INSERT OR IGNORE INTO weekview_versions"
                    "(tenant_id,department_id,year,week,version) "
                    "VALUES('1','d2',2025,10,0)"
                )
            )
            db.commit()
        finally:
            db.close()

    client: FlaskClient = app.test_client()
    with client.session_transaction() as s:
        s["role"] = "admin"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
        s["site_id"] = "s2"

    etag = client.get(
        "/api/weekview/etag?department_id=d2&year=2025&week=10"
    ).get_json()["etag"]
    response = client.post(
        "/api/weekview/specialdiets/mark",
        json={
            "year": 2025,
            "week": 10,
            "department_id": "d2",
            "meal": "Lunch",
            "weekday_abbr": "Mån",
            "diet_type_id": "Gluten",
            "marked": True,
        },
        headers={"If-Match": etag, "X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 403
