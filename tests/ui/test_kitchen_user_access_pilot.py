import uuid
from datetime import date as _date

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.db import get_session
from core.weekview.repo import WeekviewRepo
from core.weekview.service import WeekviewService


def _h(role: str):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def _seed_site(site_id: str):
    db = get_session()
    try:
        db.execute(
            text("INSERT INTO sites (id, name, tenant_id, version) VALUES (:id, :name, 1, 0)"),
            {"id": site_id, "name": "Pilot Site"},
        )
        db.commit()
    finally:
        db.close()


def _seed_weekview_inputs(site_id: str):
    dep_id = f"dep-{uuid.uuid4()}"
    diet_id = f"diet-{uuid.uuid4()}"
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                "VALUES (:id, :site_id, :name, 'fixed', 8, 0)"
            ),
            {"id": dep_id, "site_id": site_id, "name": "Avd Pilot"},
        )
        db.commit()
    finally:
        db.close()
    return dep_id, diet_id


def test_kitchen_role_redirected_from_admin_root(client_user):
    resp = client_user.get("/ui/admin", headers=_h("kitchen"), follow_redirects=False)

    assert resp.status_code in (301, 302)
    assert "/ui/kitchen" in (resp.headers.get("Location") or "")


def test_kitchen_role_redirected_from_admin_subpath(client_user):
    resp = client_user.get("/ui/admin/users", headers=_h("kitchen"), follow_redirects=False)

    assert resp.status_code in (301, 302)
    assert "/ui/kitchen" in (resp.headers.get("Location") or "")


def test_kitchen_role_can_open_kitchen_dashboard(client_user):
    resp = client_user.get("/ui/kitchen", headers=_h("kitchen"), follow_redirects=False)

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Kök" in html or "Översikt" in html
    assert "← Admin" not in html


def test_admin_sees_back_to_admin_link_in_kitchen_portal_header(client_admin):
    resp = client_admin.get("/ui/kitchen", headers=_h("admin"), follow_redirects=False)

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "← Admin" in html
    assert 'href="/ui/admin"' in html


def test_admin_can_create_and_deactivate_kitchen_user(client_admin):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    create_resp = client_admin.post(
        "/ui/admin/kitchen-users",
        headers=_h("admin"),
        data={
            "name": "Kitchen Pilot",
            "email": "kitchen.pilot@example.com",
            "password": "pilotpass123",
            "role": "kitchen",
        },
        follow_redirects=True,
    )
    assert create_resp.status_code == 200
    html = create_resp.data.decode("utf-8")
    assert "kitchen.pilot@example.com" in html

    db = get_session()
    try:
        cols = db.execute(text("PRAGMA table_info(users)")).fetchall()
        has_site_id = any(str(c[1]) == "site_id" for c in cols)
        if has_site_id:
            row = db.execute(
                text("SELECT id, role, is_active, site_id FROM users WHERE email=:e"),
                {"e": "kitchen.pilot@example.com"},
            ).fetchone()
        else:
            row = db.execute(
                text("SELECT id, role, is_active FROM users WHERE email=:e"),
                {"e": "kitchen.pilot@example.com"},
            ).fetchone()
        assert row is not None
        user_id = int(row[0])
        assert str(row[1]) == "kitchen"
        assert int(row[2]) == 1
        if has_site_id:
            assert str(row[3]) == site_id
    finally:
        db.close()

    del_resp = client_admin.post(
        f"/ui/admin/kitchen-users/{user_id}/delete",
        headers=_h("admin"),
        follow_redirects=True,
    )
    assert del_resp.status_code == 200

    db = get_session()
    try:
        row2 = db.execute(text("SELECT is_active FROM users WHERE id=:uid"), {"uid": user_id}).fetchone()
        assert row2 is not None
        assert int(row2[0]) == 0
    finally:
        db.close()


def test_ui_login_redirects_kitchen_user_to_kitchen_portal(client_admin):
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                "VALUES (1, :email, :password_hash, 'kitchen', :username, :full_name, 1)"
            ),
            {
                "email": "kitchen.login@example.com",
                "password_hash": generate_password_hash("kitchen-pass"),
                "username": "kitchen.login@example.com",
                "full_name": "Kitchen Login",
            },
        )
        db.commit()
    finally:
        db.close()

    resp = client_admin.post(
        "/ui/login",
        data={"email": "kitchen.login@example.com", "password": "kitchen-pass"},
        follow_redirects=False,
    )

    assert resp.status_code in (301, 302)
    assert "/ui/kitchen" in (resp.headers.get("Location") or "")


def test_admin_dashboard_has_open_kitchen_portal_button(client_admin):
    resp = client_admin.get("/ui/admin", headers=_h("admin"))

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Öppna köksportal" in html
    assert "href=\"/ui/kitchen\"" in html


def test_kitchen_role_can_open_kitchen_weekview(client_user):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)

    with client_user.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_user.get(f"/ui/kitchen/week?site_id={site_id}", headers=_h("kitchen"), follow_redirects=False)

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Veckovy" in html


def test_kitchen_role_can_mark_weekview_specialdiet(client_user):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    dep_id, diet_id = _seed_weekview_inputs(site_id)

    with client_user.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["tenant_id"] = 1

    iso = _date.today().isocalendar()
    year, week = int(iso[0]), int(iso[1])

    etag_resp = client_user.get(
        f"/api/weekview/etag?department_id={dep_id}&year={year}&week={week}&site_id={site_id}",
        headers=_h("kitchen"),
    )
    assert etag_resp.status_code == 200
    etag = (etag_resp.get_json() or {}).get("etag")
    assert etag

    mark_resp = client_user.post(
        "/api/weekview/specialdiets/mark",
        headers={**_h("kitchen"), "If-Match": etag},
        json={
            "year": year,
            "week": week,
            "department_id": dep_id,
            "diet_type_id": diet_id,
            "meal": "Lunch",
            "weekday_abbr": "Mån",
            "marked": True,
            "site_id": site_id,
        },
    )

    assert mark_resp.status_code == 200

    payload = WeekviewRepo().get_weekview(tenant_id=1, year=year, week=week, department_id=dep_id)
    marks = ((payload.get("department_summaries") or [{}])[0].get("marks") or [])
    assert any(
        int(m.get("day_of_week") or 0) == 1
        and str(m.get("meal") or "") == "lunch"
        and str(m.get("diet_type") or "") == str(diet_id)
        and bool(m.get("marked"))
        for m in marks
    )


def test_kitchen_role_blocked_from_admin_and_systemadmin(client_user):
    resp_admin = client_user.get("/ui/admin/departments", headers=_h("kitchen"), follow_redirects=False)
    assert resp_admin.status_code in (301, 302)
    assert "/ui/kitchen" in (resp_admin.headers.get("Location") or "")

    resp_system = client_user.get("/ui/systemadmin/dashboard", headers=_h("kitchen"), follow_redirects=False)
    assert resp_system.status_code == 403


def test_admin_weekview_mark_behavior_unchanged(client_admin):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    dep_id, diet_id = _seed_weekview_inputs(site_id)

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["tenant_id"] = 1

    iso = _date.today().isocalendar()
    year, week = int(iso[0]), int(iso[1])

    etag = WeekviewService().build_etag(
        tenant_id=1,
        department_id=dep_id,
        year=year,
        week=week,
        version=WeekviewRepo().get_version(tenant_id=1, year=year, week=week, department_id=dep_id),
    )

    resp = client_admin.post(
        "/api/weekview/specialdiets/mark",
        headers={**_h("admin"), "If-Match": etag},
        json={
            "year": year,
            "week": week,
            "department_id": dep_id,
            "diet_type_id": diet_id,
            "meal": "Lunch",
            "weekday_abbr": "Mån",
            "marked": True,
            "site_id": site_id,
        },
    )
    assert resp.status_code == 200
