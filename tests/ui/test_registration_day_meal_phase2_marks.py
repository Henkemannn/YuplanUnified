import re
from datetime import date as _date
from flask.testing import FlaskClient
from sqlalchemy import text

ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
USER = {"X-User-Role": "user", "X-Tenant-Id": "1"}


def _enable_flags(client: FlaskClient):
    # Enable weekview + registration phase2
    for name in ("ff.weekview.enabled", "ff.registration.phase2.enabled"):
        r = client.post(
            "/features/set",
            json={"name": name, "enabled": True},
            headers=ADMIN,
        )
        assert r.status_code == 200


def _seed_phase2(site_id: str, dep_id: str, date_str: str):
    from core.db import get_session
    from core.models import DietaryType

    db = get_session()
    try:
        # Basic site/department
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT)"))
        db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')"))
        db.execute(text("INSERT OR REPLACE INTO sites(id, tenant_id, name) VALUES(:i,1,'Site A')"), {"i": site_id})
        db.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES(:i,:s,'Avd A','manual')"), {"i": dep_id, "s": site_id})
        gluten = DietaryType(tenant_id=1, site_id=site_id, name="Glutenfri")
        laktos = DietaryType(tenant_id=1, site_id=site_id, name="Laktosfri")
        db.add_all([gluten, laktos])
        db.flush()
        gluten_id = str(gluten.id)
        laktos_id = str(laktos.id)
        # Residents count for lunch
        db.execute(text("CREATE TABLE IF NOT EXISTS residents_counts(site_id TEXT, department_id TEXT, date TEXT, lunch INTEGER, dinner INTEGER)"))
        db.execute(text("INSERT OR REPLACE INTO residents_counts(site_id, department_id, date, lunch, dinner) VALUES(:s,:d,:dt,10,8)"), {"s": site_id, "d": dep_id, "dt": date_str})
        # Planned defaults via department_diet_defaults
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS department_diet_defaults (
              department_id TEXT NOT NULL,
              diet_type_id TEXT NOT NULL,
              default_count INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (department_id, diet_type_id)
            )
            """
        ))
        db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:diet,2)"), {"d": dep_id, "diet": gluten_id})
        db.execute(text("INSERT OR REPLACE INTO department_diet_defaults(department_id, diet_type_id, default_count) VALUES(:d,:diet,1)"), {"d": dep_id, "diet": laktos_id})
        db.commit()
        assert db.execute(
            text("SELECT id,site_id,name FROM dietary_types WHERE site_id=:site ORDER BY name"),
            {"site": site_id},
        ).all()
        from core.admin_repo import DietDefaultsRepo, DietTypesRepo

        assert [item["name"] for item in DietTypesRepo().list_all(site_id=site_id)] == [
            "Glutenfri",
            "Laktosfri",
        ]
        assert {item["diet_type_id"] for item in DietDefaultsRepo().list_for_department(dep_id)} == {
            gluten_id,
            laktos_id,
        }
        return gluten_id
    finally:
        db.close()


def _extract_etag(html: str) -> str | None:
    # Prefer data-weekview-etag on summary card (fallback if no header)
    m = re.search(r'data-weekview-etag=\"([^\"]+)\"', html)
    if m:
        return m.group(1)
    m2 = re.search(r'name=\"_etag\" value=\"([^\"]+)\"', html)
    return m2.group(1) if m2 else None


def test_phase2_toggle_mark_on_off_happy_path(app_session):
    client = app_session.test_client()
    _enable_flags(client)

    site_id = "00000000-0000-0000-0000-00000000a111"
    dep_id = "00000000-0000-0000-0000-00000000b222"
    date_str = "2025-12-02"
    meal = "lunch"
    gluten_id = _seed_phase2(site_id, dep_id, date_str)
    with client.session_transaction() as sess:
        sess["site_id"] = site_id

    # Initial GET
    r0 = client.get(
        f"/ui/register/meal?site_id={site_id}&department_id={dep_id}&date={date_str}&meal={meal}",
        headers=ADMIN,
    )
    assert r0.status_code == 200
    body0 = r0.get_data(as_text=True)
    assert "Glutenfri" in body0 and "Laktosfri" in body0, body0
    # Planned counts visible
    assert ">2<" in body0 and ">1<" in body0
    # No marked class initially (avoid matching CSS selector text)
    assert re.search(r"<span[^>]+class=\"[^\"]*diet-count--marked[^\"]*\"", body0) is None
    etag0 = r0.headers.get("ETag") or _extract_etag(body0)
    assert etag0

    # Toggle mark ON for Glutenfri
    resp_on = client.post(
        "/ui/register/meal/toggle-mark",
        data={
            "site_id": site_id,
            "department_id": dep_id,
            "date": date_str,
            "meal": meal,
            "diet_type_id": gluten_id,
            "_etag": etag0,
        },
        headers=ADMIN,
        follow_redirects=True,
    )
    assert resp_on.status_code in (200, 302)
    body1 = resp_on.get_data(as_text=True)
    assert re.search(r"<span[^>]+class=\"[^\"]*diet-count--marked[^\"]*\"", body1)
    # Planned counts unchanged
    assert ">2<" in body1 and ">1<" in body1
    etag1 = resp_on.headers.get("ETag") or _extract_etag(body1)
    assert etag1 and etag1 != etag0

    # Toggle mark OFF for Glutenfri with fresh ETag
    resp_off = client.post(
        "/ui/register/meal/toggle-mark",
        data={
            "site_id": site_id,
            "department_id": dep_id,
            "date": date_str,
            "meal": meal,
            "diet_type_id": gluten_id,
            "_etag": etag1,
        },
        headers=ADMIN,
        follow_redirects=True,
    )
    assert resp_off.status_code in (200, 302)
    body2 = resp_off.get_data(as_text=True)
    assert re.search(r"<span[^>]+class=\"[^\"]*diet-count--marked[^\"]*\"", body2) is None
    # Planned counts still unchanged
    assert ">2<" in body2 and ">1<" in body2


def test_phase2_etag_stale_returns_412(app_session):
    client = app_session.test_client()
    _enable_flags(client)

    site_id = "00000000-0000-0000-0000-00000000a333"
    dep_id = "00000000-0000-0000-0000-00000000b444"
    date_str = "2025-12-03"
    meal = "lunch"
    gluten_id = _seed_phase2(site_id, dep_id, date_str)
    with client.session_transaction() as sess:
        sess["site_id"] = site_id

    r0 = client.get(
        f"/ui/register/meal?site_id={site_id}&department_id={dep_id}&date={date_str}&meal={meal}",
        headers=ADMIN,
    )
    assert r0.status_code == 200
    etag_old = r0.headers.get("ETag") or _extract_etag(r0.get_data(as_text=True))
    assert etag_old

    # First toggle to advance ETag
    r1 = client.post(
        "/ui/register/meal/toggle-mark",
        data={
            "site_id": site_id,
            "department_id": dep_id,
            "date": date_str,
            "meal": meal,
            "diet_type_id": gluten_id,
            "_etag": etag_old,
        },
        headers=ADMIN,
    )
    assert r1.status_code in (200, 302)
    # Now try with stale ETag again
    r2 = client.post(
        "/ui/register/meal/toggle-mark",
        data={
            "site_id": site_id,
            "department_id": dep_id,
            "date": date_str,
            "meal": meal,
            "diet_type_id": gluten_id,
            "_etag": etag_old,
        },
        headers=ADMIN,
    )
    assert r2.status_code == 412
    body = r2.get_data(as_text=True)
    assert "etag" in body.lower()


def test_phase2_rbac_enforced_on_toggle(app_session):
    client = app_session.test_client()
    _enable_flags(client)

    site_id = "00000000-0000-0000-0000-00000000a555"
    dep_id = "00000000-0000-0000-0000-00000000b666"
    date_str = "2025-12-04"
    meal = "lunch"
    gluten_id = _seed_phase2(site_id, dep_id, date_str)
    with client.session_transaction() as sess:
        sess["site_id"] = site_id

    r0 = client.get(
        f"/ui/register/meal?site_id={site_id}&department_id={dep_id}&date={date_str}&meal={meal}",
        headers=ADMIN,
    )
    assert r0.status_code == 200
    etag = r0.headers.get("ETag") or _extract_etag(r0.get_data(as_text=True))
    assert etag

    # User without SAFE_UI_ROLES tries to toggle
    r_forbidden = client.post(
        "/ui/register/meal/toggle-mark",
        data={
            "site_id": site_id,
            "department_id": dep_id,
            "date": date_str,
            "meal": meal,
            "diet_type_id": gluten_id,
            "_etag": etag,
        },
        headers=USER,
    )
    assert r_forbidden.status_code in (401, 403)
