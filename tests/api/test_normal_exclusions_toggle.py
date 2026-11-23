import uuid

from sqlalchemy import text
from werkzeug.security import generate_password_hash

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _ensure_site_and_diet(site_id: str) -> tuple[str, str]:
    from core.admin_repo import SitesRepo, DietTypesRepo
    srepo = SitesRepo()
    site, _ = srepo.create_site("Toggle Site", tenant_id=1)
    actual_site_id = str(site["id"])
    trepo = DietTypesRepo()
    diet_id = trepo.create(site_id=actual_site_id, name="Laktos", default_select=False)
    return actual_site_id, str(diet_id)


def _login_real_user(app_session, client, *, site_id: str, role: str) -> None:
    from core.db import get_session
    email = f"normal-exclusion-{uuid.uuid4().hex}@example.test"
    password = "NormalExclusionPassw0rd!2026"
    with app_session.app_context():
        db = get_session()
        try:
            from core.models import User

            user = User(
                tenant_id=1,
                email=email,
                username=email,
                password_hash=generate_password_hash(password),
                auth_version=1,
                role=role,
                full_name="Normal Exclusion Auth User",
                is_active=True,
            )
            db.add(user)
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites "
                    "(user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            db.flush()
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:user_id, 1, :site_id)"
                ),
                {"user_id": int(user.id), "site_id": site_id},
            )
            db.commit()
        finally:
            db.close()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, response.get_json()


def test_toggle_normal_exclusion_insert_then_remove(app_session):
    client = app_session.test_client()
    site_id, diet_id = _ensure_site_and_diet("site-normal-exc-1")
    _login_real_user(app_session, client, site_id=site_id, role="admin")
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS normal_exclusions (
              tenant_id TEXT NOT NULL,
              site_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              day_index INTEGER NOT NULL,
              meal TEXT NOT NULL,
              alt TEXT NOT NULL,
              diet_type_id TEXT NOT NULL,
              UNIQUE (tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
            );
            """
        ))
        db.commit()
    finally:
        db.close()

    payload = {
        "site_id": site_id,
        "year": 2026,
        "week": 6,
        "day_index": 3,
        "meal": "lunch",
        "alt": "1",
        "diet_type_id": diet_id,
    }
    # First toggle -> insert
    rv = client.post("/api/kitchen/planering/normal_exclusions/toggle", json=payload)
    assert rv.status_code == 200
    data = rv.get_json()
    assert data and data.get("excluded") is True
    # Verify row exists
    db = get_session()
    try:
        row = db.execute(text(
            "SELECT COUNT(1) FROM normal_exclusions WHERE tenant_id=:tid AND site_id=:s AND year=:y AND week=:w AND day_index=:d AND meal=:m AND alt=:a AND diet_type_id=:dt"
        ), {"tid": "1", "s": site_id, "y": 2026, "w": 6, "d": 3, "m": "lunch", "a": "1", "dt": diet_id}).fetchone()
        assert int(row[0]) == 1
    finally:
        db.close()

    # Second toggle -> delete
    rv2 = client.post("/api/kitchen/planering/normal_exclusions/toggle", json=payload)
    assert rv2.status_code == 200
    data2 = rv2.get_json()
    assert data2 and data2.get("excluded") is False
    # Verify row removed
    db = get_session()
    try:
        row2 = db.execute(text(
            "SELECT COUNT(1) FROM normal_exclusions WHERE tenant_id=:tid AND site_id=:s AND year=:y AND week=:w AND day_index=:d AND meal=:m AND alt=:a AND diet_type_id=:dt"
        ), {"tid": "1", "s": site_id, "y": 2026, "w": 6, "d": 3, "m": "lunch", "a": "1", "dt": diet_id}).fetchone()
        assert int(row2[0]) == 0
    finally:
        db.close()


def test_toggle_normal_exclusion_allows_kitchen_role(app_session):
    client = app_session.test_client()
    site_id, diet_id = _ensure_site_and_diet("site-normal-exc-kitchen")
    _login_real_user(app_session, client, site_id=site_id, role="kitchen")
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS normal_exclusions (
              tenant_id TEXT NOT NULL,
              site_id TEXT NOT NULL,
              year INTEGER NOT NULL,
              week INTEGER NOT NULL,
              day_index INTEGER NOT NULL,
              meal TEXT NOT NULL,
              alt TEXT NOT NULL,
              diet_type_id TEXT NOT NULL,
              UNIQUE (tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
            );
            """
        ))
        db.commit()
    finally:
        db.close()

    payload = {
        "site_id": site_id,
        "year": 2026,
        "week": 7,
        "day_index": 1,
        "meal": "lunch",
        "alt": "1",
        "diet_type_id": diet_id,
    }

    rv = client.post(
        "/api/kitchen/planering/normal_exclusions/toggle",
        json=payload,
    )
    assert rv.status_code == 200
    data = rv.get_json() or {}
    assert data.get("excluded") is True
