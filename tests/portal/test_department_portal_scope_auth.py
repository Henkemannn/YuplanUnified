from __future__ import annotations

import pytest
from sqlalchemy import text


YEAR = 2025
WEEK = 47


def _headers(role: str, user_id: int, tenant_id: int = 1) -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": str(tenant_id), "X-User-Id": str(user_id)}


def _seed_user(db, *, user_id: int, tenant_id: int, role: str, department_id: str | None) -> None:
    db.execute(
        text(
            "INSERT OR REPLACE INTO users(id, tenant_id, username, email, password_hash, role, full_name, is_active, department_id) "
            "VALUES(:id, :tid, :username, :email, 'hash', :role, :full_name, 1, :department_id)"
        ),
        {
            "id": user_id,
            "tid": tenant_id,
            "username": f"user-{user_id}",
            "email": f"user-{user_id}@example.com",
            "role": role,
            "full_name": f"User {user_id}",
            "department_id": department_id,
        },
    )


def _seed_scope(db, *, dept_id: str, site_id: str, tenant_id: int, tenant_name: str = "Tenant") -> None:
    db.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, tenant_id INTEGER, version INTEGER)"))
    db.execute(
        text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT, notes TEXT NULL, resident_count_mode TEXT NOT NULL DEFAULT 'manual')")
    )
    db.execute(text("INSERT OR REPLACE INTO tenants(id,name,active) VALUES(:id,:name,1)"), {"id": tenant_id, "name": tenant_name})
    db.execute(
        text("INSERT OR REPLACE INTO sites(id,name,tenant_id,version) VALUES(:id,:name,:tid,0)"),
        {"id": site_id, "name": f"Site {tenant_id}", "tid": tenant_id},
    )
    db.execute(
        text("INSERT OR REPLACE INTO departments(id,site_id,name,notes,resident_count_mode) VALUES(:id,:sid,:name,:notes,'manual')"),
        {"id": dept_id, "sid": site_id, "name": "Avd 1", "notes": "Inga risrätter"},
    )


def test_unit_portal_scope_uses_bound_department_and_ignores_client_overrides(
    client_admin,
    seed_portal_department_data,
    seed_canonical_builder_publication,
    seed_portal_menu_choice,
):
    dept_id = "11111111-2222-3333-4444-555555555555"
    site_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=YEAR, week=WEEK)
    seed_canonical_builder_publication(site_id=site_id, year=YEAR, week=WEEK)
    seed_portal_menu_choice(
        tenant_id=1,
        site_id=site_id,
        department_id=dept_id,
        year=YEAR,
        week=WEEK,
        weekday=1,
        selected_variant="Alt2",
    )
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_user(conn, user_id=11, tenant_id=1, role="unit_portal", department_id=dept_id)
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.get(
        f"/portal/department/week?year={YEAR}&week={WEEK}&tenant_id=999&site_id=wrong-site&department_id=wrong-dept",
        headers=_headers("unit_portal", 11),
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["department_id"] == dept_id
    assert payload["site_id"] == site_id


def test_unit_portal_cross_tenant_department_denied(client_admin):
    dept_id = "22222222-3333-4444-5555-666666666666"
    site_id = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_scope(conn, dept_id=dept_id, site_id=site_id, tenant_id=2, tenant_name="Tenant Two")
            _seed_user(conn, user_id=12, tenant_id=1, role="unit_portal", department_id=dept_id)
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.get(
        f"/portal/department/week?year={YEAR}&week={WEEK}",
        headers=_headers("unit_portal", 12, tenant_id=1),
    )
    assert resp.status_code == 403


def test_unit_portal_null_department_denied(client_admin):
    dept_id = "33333333-4444-5555-6666-777777777777"
    site_id = "cccccccc-dddd-eeee-ffff-000000000000"
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_scope(conn, dept_id=dept_id, site_id=site_id, tenant_id=1)
            _seed_user(conn, user_id=13, tenant_id=1, role="unit_portal", department_id=None)
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.get(
        f"/portal/department/week?year={YEAR}&week={WEEK}",
        headers=_headers("unit_portal", 13),
    )
    assert resp.status_code == 403


def test_unit_portal_unknown_department_denied(client_admin):
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_user(conn, user_id=14, tenant_id=1, role="unit_portal", department_id="missing-dept")
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.get(
        f"/portal/department/week?year={YEAR}&week={WEEK}",
        headers=_headers("unit_portal", 14),
    )
    assert resp.status_code == 403


@pytest.mark.parametrize(
    ("dept_site_id", "create_site_row", "site_tenant_id"),
    [
        ("missing-site", False, None),
        ("site-missing-tenant", True, None),
    ],
)
def test_unit_portal_invalid_department_site_denied(client_admin, dept_site_id, create_site_row, site_tenant_id):
    dept_id = f"dept-{dept_site_id}"
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            conn.execute(text("CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT, active INTEGER)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, tenant_id INTEGER, version INTEGER)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT, resident_count_mode TEXT NOT NULL DEFAULT 'manual')"))
            if create_site_row:
                if site_tenant_id is not None:
                    conn.execute(text("INSERT OR REPLACE INTO sites(id,name,tenant_id,version) VALUES(:id,:name,:tid,0)"), {"id": dept_site_id, "name": "Site", "tid": site_tenant_id})
                else:
                    conn.execute(text("INSERT OR REPLACE INTO sites(id,name,tenant_id,version) VALUES(:id,:name,NULL,0)"), {"id": dept_site_id, "name": "Site"})
            conn.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode) VALUES(:id,:sid,:name,'manual')"), {"id": dept_id, "sid": dept_site_id, "name": "Avd"})
            _seed_user(conn, user_id=15, tenant_id=1, role="unit_portal", department_id=dept_id)
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.get(
        f"/portal/department/week?year={YEAR}&week={WEEK}",
        headers=_headers("unit_portal", 15),
    )
    assert resp.status_code == 403


def test_admin_support_can_open_department_portal_within_tenant(
    client_admin,
    seed_portal_department_data,
    seed_canonical_builder_publication,
):
    dept_id = "44444444-5555-6666-7777-888888888888"
    site_id = "dddddddd-eeee-ffff-0000-111111111111"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=YEAR, week=WEEK)
    seed_canonical_builder_publication(site_id=site_id, year=YEAR, week=WEEK)
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_user(conn, user_id=16, tenant_id=1, role="admin", department_id=None)
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.get(
        f"/ui/portal/department/week?year={YEAR}&week={WEEK}&department_id={dept_id}",
        headers=_headers("admin", 16),
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert dept_id in html


def test_admin_cross_tenant_scope_denied(client_admin):
    dept_id = "55555555-6666-7777-8888-999999999999"
    site_id = "eeeeeeee-ffff-0000-1111-222222222222"
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_scope(conn, dept_id=dept_id, site_id=site_id, tenant_id=2, tenant_name="Tenant Two")
            _seed_user(conn, user_id=17, tenant_id=1, role="admin", department_id=None)
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.get(
        f"/ui/portal/department/week?year={YEAR}&week={WEEK}&department_id={dept_id}",
        headers=_headers("admin", 17, tenant_id=1),
    )
    assert resp.status_code == 403


def test_unit_portal_menu_choice_mutation_uses_canonical_scope(
    client_admin,
    seed_portal_department_data,
    seed_canonical_builder_publication,
    seed_portal_menu_choice,
):
    dept_id = "66666666-7777-8888-9999-aaaaaaaaaaaa"
    site_id = "ffffffff-0000-1111-2222-333333333333"
    seed_portal_department_data(dept_id=dept_id, site_id=site_id, year=YEAR, week=WEEK)
    seed_canonical_builder_publication(site_id=site_id, year=YEAR, week=WEEK)
    seed_portal_menu_choice(
        tenant_id=1,
        site_id=site_id,
        department_id=dept_id,
        year=YEAR,
        week=WEEK,
        weekday=1,
        selected_variant="Alt1",
    )
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_user(conn, user_id=18, tenant_id=1, role="unit_portal", department_id=dept_id)
            conn.commit()
        finally:
            conn.close()

    read_resp = client_admin.get(
        f"/portal/department/week?year={YEAR}&week={WEEK}&tenant_id=999&site_id=wrong-site&department_id=wrong-dept",
        headers=_headers("unit_portal", 18),
    )
    assert read_resp.status_code == 200
    etag = read_resp.get_json()["etag_map"]["menu_choice"]

    write_resp = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Mon", "selected_alt": "Alt2"},
        headers={**_headers("unit_portal", 18), "If-Match": etag},
    )
    assert write_resp.status_code == 200
    assert write_resp.get_json()["selected_alt"] == "Alt2"


def test_admin_cross_tenant_menu_choice_mutation_denied(client_admin):
    dept_id = "77777777-8888-9999-aaaa-bbbbbbbbbbbb"
    site_id = "11111111-2222-3333-4444-555555555555"
    db = client_admin.application
    with db.app_context():
        from core.db import get_session

        conn = get_session()
        try:
            _seed_scope(conn, dept_id=dept_id, site_id=site_id, tenant_id=2, tenant_name="Tenant Two")
            _seed_user(conn, user_id=19, tenant_id=1, role="admin", department_id=None)
            conn.commit()
        finally:
            conn.close()

    resp = client_admin.post(
        "/portal/department/menu-choice/change",
        json={"year": YEAR, "week": WEEK, "weekday": "Mon", "selected_alt": "Alt2"},
        headers={**_headers("admin", 19), "If-Match": 'W/"noop"'},
    )
    assert resp.status_code == 403
