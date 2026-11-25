import uuid

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.db import get_session
from core.models import Department, Site, Tenant, User
from core.weekview.service import WeekviewService


def _seed_scope(app_session):
    suffix = uuid.uuid4().hex
    with app_session.app_context():
        db = get_session()
        try:
            for tenant_id in (1, 2):
                if db.query(Tenant).filter_by(id=tenant_id).first() is None:
                    db.add(Tenant(id=tenant_id, name=f"F09 Tenant {tenant_id}"))
            site_a = Site(id=f"f09-a-{suffix}", name="F09 Site A", tenant_id=1)
            site_b = Site(id=f"f09-b-{suffix}", name="F09 Site B", tenant_id=1)
            site_c = Site(id=f"f09-c-{suffix}", name="F09 Site C", tenant_id=2)
            db.add_all([site_a, site_b, site_c])
            department_a = Department(
                id=str(uuid.uuid4()),
                site_id=site_a.id,
                name="F09 Department A",
            )
            department_b = Department(
                id=str(uuid.uuid4()),
                site_id=site_b.id,
                name="F09 Department B",
            )
            department_c = Department(
                id=str(uuid.uuid4()),
                site_id=site_c.id,
                name="F09 Department C",
            )
            db.add_all([department_a, department_b, department_c])
            email = f"f09-admin-{suffix}@example.test"
            password = "F09RemainingPassw0rd!2026"
            actor = User(
                tenant_id=1,
                email=email,
                username=email,
                password_hash=generate_password_hash(password),
                role="admin",
                auth_version=1,
                is_active=True,
            )
            db.add(actor)
            db.flush()
            superuser_email = f"f09-superuser-{suffix}@example.test"
            superuser_password = "F09SuperuserPassw0rd!2026"
            db.add(
                User(
                    tenant_id=1,
                    email=superuser_email,
                    username=superuser_email,
                    password_hash=generate_password_hash(superuser_password),
                    role="superuser",
                    auth_version=1,
                    is_active=True,
                )
            )
            db.flush()
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            next_user_id = int(
                db.execute(
                    text(
                        "SELECT MAX(candidate_id) + 1 FROM ("
                        "SELECT COALESCE(MAX(id), 0) AS candidate_id FROM users "
                        "UNION ALL "
                        "SELECT COALESCE(MAX(user_id), 0) AS candidate_id "
                        "FROM kitchen_user_sites"
                        ")"
                    )
                ).scalar_one()
            )
            actor.id = next_user_id
            db.flush()
            db.commit()
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                    "VALUES (:user_id, :tenant_id, :site_id)"
                ),
                {"user_id": actor.id, "tenant_id": 1, "site_id": site_a.id},
            )
            db.commit()
            return {
                "email": email,
                "password": password,
                "superuser_email": superuser_email,
                "superuser_password": superuser_password,
                "actor_id": actor.id,
                "site_a": site_a.id,
                "site_b": site_b.id,
                "site_c": site_c.id,
                "department_a": department_a.id,
                "department_b": department_b.id,
                "department_c": department_c.id,
            }
        finally:
            db.close()


def _login(client, data):
    response = client.post(
        "/auth/login",
        json={"email": data["email"], "password": data["password"]},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)


def _set_site_lock(client, value):
    with client.session_transaction() as session:
        if value is None:
            session.pop("site_lock", None)
        else:
            session["site_lock"] = value


def _weekview_etag(tenant_id, department_id, year=2026, week=12):
    service = WeekviewService()
    version = service.repo.get_version(tenant_id, year, week, department_id)
    return service.build_etag(tenant_id, department_id, year, week, version)


@pytest.mark.parametrize("site_lock", [True, False, None])
def test_real_user_cannot_mutate_foreign_weekview_departments(
    app_session, site_lock
):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    client.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    _login(client, data)
    _set_site_lock(client, site_lock)

    before = _weekview_etag(1, data["department_b"])
    requests = [
        (
            "/api/weekview",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "year": 2026,
                "week": 12,
                "operations": [
                    {
                        "day_of_week": 1,
                        "meal": "lunch",
                        "diet_type": "normal",
                        "marked": True,
                    }
                ],
            },
        ),
        (
            "/api/weekview/residents",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "year": 2026,
                "week": 12,
                "items": [{"day_of_week": 1, "meal": "lunch", "count": 9}],
            },
        ),
        (
            "/api/weekview/alt2",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "year": 2026,
                "week": 12,
                "days": [1],
            },
        ),
        (
            "/api/weekview/specialdiets/mark",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "local_date": "2026-03-16",
                "meal": "lunch",
                "diet_type_id": "f09-diet",
                "marked": True,
            },
        ),
    ]
    for path, payload in requests:
        response = client.patch(path, json=payload, headers={"If-Match": before})
        assert response.status_code == 403
        payload_without_site = dict(payload)
        payload_without_site.pop("site_id", None)
        response = client.patch(
            path,
            json=payload_without_site,
            headers={"If-Match": before},
        )
        assert response.status_code == 403

    assert _weekview_etag(1, data["department_b"]) == before

    for path, payload in requests:
        foreign_payload = dict(payload)
        foreign_payload.pop("site_id", None)
        foreign_payload["department_id"] = data["department_c"]
        foreign_before = _weekview_etag(2, data["department_c"])
        response = client.patch(
            path,
            json=foreign_payload,
            headers={"If-Match": foreign_before},
        )
        assert response.status_code == 403
        assert _weekview_etag(2, data["department_c"]) == foreign_before


def test_real_admin_scope_guard_runs_for_all_weekview_mutations(
    app_session, monkeypatch
):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data)
    calls = []
    from core import weekview_api

    original = weekview_api.resolve_department_scope

    def scope_spy(department_id, tenant_id, active_site_id):
        calls.append((department_id, tenant_id, active_site_id))
        return original(department_id, tenant_id, active_site_id)

    monkeypatch.setattr(weekview_api, "resolve_department_scope", scope_spy)
    requests = [
        (
            "/api/weekview",
            {
                "department_id": data["department_b"],
                "year": 2026,
                "week": 20,
                "operations": [],
            },
        ),
        (
            "/api/weekview/residents",
            {
                "department_id": data["department_b"],
                "year": 2026,
                "week": 20,
                "items": [],
            },
        ),
        (
            "/api/weekview/alt2",
            {
                "department_id": data["department_b"],
                "year": 2026,
                "week": 20,
                "days": [],
            },
        ),
        (
            "/api/weekview/specialdiets/mark",
            {
                "department_id": data["department_b"],
                "local_date": "2026-05-18",
                "meal": "lunch",
                "diet_type_id": "f09-diet",
                "marked": True,
            },
        ),
    ]
    for path, payload in requests:
        headers = {}
        if path != "/api/weekview/specialdiets/mark":
            headers["If-Match"] = _weekview_etag(1, data["department_b"], 2026, 20)
        response = client.patch(path, json=payload, headers=headers)
        assert response.status_code == 403
    assert len(calls) == 4
    assert all(call[0] == data["department_b"] for call in calls)


def test_real_user_cannot_create_version_for_foreign_specialdiet_without_if_match(
    app_session,
):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    client.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    _login(client, data)
    response = client.patch(
        "/api/weekview/specialdiets/mark",
        json={
            "site_id": data["site_b"],
            "department_id": data["department_b"],
            "local_date": "2026-03-16",
            "meal": "lunch",
            "diet_type_id": "f09-diet",
            "marked": True,
        },
    )
    assert response.status_code == 403
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(
                text(
                    "SELECT version FROM weekview_versions "
                    "WHERE tenant_id=:tenant_id AND department_id=:department_id "
                    "AND year=:year AND week=:week"
                ),
                {
                    "tenant_id": "1",
                    "department_id": data["department_b"],
                    "year": 2026,
                    "week": 12,
                },
            ).fetchone()
            assert row is None
        finally:
            db.close()


def test_real_residents_write_uses_authorized_resolved_site(
    app_session, monkeypatch
):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data)
    captured = {}

    def spy(*args):
        captured["site_id"] = args[-1]
        return args[4]

    monkeypatch.setattr(
        "core.weekview_api._service.update_residents_counts",
        spy,
    )
    response = client.patch(
        "/api/weekview/residents",
        json={
            "department_id": data["department_a"],
            "year": 2026,
            "week": 12,
            "items": [{"day_of_week": 1, "meal": "lunch", "count": 3}],
        },
        headers={"If-Match": _weekview_etag(1, data["department_a"])},
    )
    assert response.status_code == 200
    assert captured["site_id"] == data["site_a"]


def test_real_user_can_mutate_all_own_weekview_endpoints(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    client.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    _login(client, data)
    requests = [
        (
            "/api/weekview",
            {
                "site_id": data["site_a"],
                "department_id": data["department_a"],
                "year": 2026,
                "week": 13,
                "operations": [
                    {
                        "day_of_week": 1,
                        "meal": "lunch",
                        "diet_type": "normal",
                        "marked": True,
                    }
                ],
            },
            True,
        ),
        (
            "/api/weekview/residents",
            {
                "site_id": data["site_a"],
                "department_id": data["department_a"],
                "year": 2026,
                "week": 14,
                "items": [{"day_of_week": 1, "meal": "lunch", "count": 4}],
            },
            True,
        ),
        (
            "/api/weekview/alt2",
            {
                "site_id": data["site_a"],
                "department_id": data["department_a"],
                "year": 2026,
                "week": 15,
                "days": [1],
            },
            True,
        ),
        (
            "/api/weekview/specialdiets/mark",
            {
                "site_id": data["site_a"],
                "department_id": data["department_a"],
                "local_date": "2026-03-16",
                "meal": "lunch",
                "diet_type_id": "f09-diet",
                "marked": True,
            },
            False,
        ),
    ]
    for path, payload, requires_etag in requests:
        headers = {}
        if requires_etag:
            headers["If-Match"] = _weekview_etag(
                1, data["department_a"], payload["year"], payload["week"]
            )
        response = client.patch(path, json=payload, headers=headers)
        assert response.status_code == 200


def test_superuser_is_denied_weekview_mutations(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    client.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    _login(
        client,
        {"email": data["superuser_email"], "password": data["superuser_password"]},
    )
    requests = [
        (
            "/api/weekview",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "year": 2026,
                "week": 16,
                "operations": [
                    {
                        "day_of_week": 1,
                        "meal": "lunch",
                        "diet_type": "normal",
                        "marked": True,
                    }
                ],
            },
        ),
        (
            "/api/weekview/residents",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "year": 2026,
                "week": 17,
                "items": [{"day_of_week": 1, "meal": "lunch", "count": 4}],
            },
        ),
        (
            "/api/weekview/alt2",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "year": 2026,
                "week": 18,
                "days": [1],
            },
        ),
        (
            "/api/weekview/specialdiets/mark",
            {
                "site_id": data["site_b"],
                "department_id": data["department_b"],
                "local_date": "2026-03-16",
                "meal": "lunch",
                "diet_type_id": "f09-diet",
                "marked": True,
            },
        ),
    ]
    for path, payload in requests:
        year = payload.get("year", 2026)
        week = payload.get("week", 12)
        before = _weekview_etag(1, data["department_b"], year, week)
        response = client.patch(
            path,
            json=payload,
            headers={"If-Match": before},
        )
        assert response.status_code == 403
        assert _weekview_etag(1, data["department_b"], year, week) == before


def test_mixed_mark_done_targets_are_rejected_atomically(app_session, monkeypatch):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data)
    calls = []

    def mark_done_spy(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("core.planera_service.PlaneraService.mark_done", mark_done_spy)
    response = client.post(
        "/ui/planera/day/mark_done",
        data={
            "site_id": data["site_a"],
            "date": "2026-03-16",
            "meal": "lunch",
            "department_ids": [data["department_a"], data["department_b"]],
        },
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize("column,value", [("is_active", 0), ("auth_version", 2)])
def test_inactive_or_revoked_user_cannot_mutate_planera(
    app_session, column, value
):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data)
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(f"UPDATE users SET {column}=:value WHERE id=:user_id"),
                {"value": value, "user_id": data["actor_id"]},
            )
            db.commit()
        finally:
            db.close()
    response = client.post(
        "/api/kitchen/planering/normal_exclusions/toggle",
        json={
            "site_id": data["site_a"],
            "year": 2026,
            "week": 18,
            "day_index": 1,
            "meal": "lunch",
            "alt": "1",
            "diet_type_id": "f09-diet",
        },
    )
    assert response.status_code in (401, 403)


def test_real_user_can_toggle_own_normal_exclusion(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data)
    response = client.post(
        "/api/kitchen/planering/normal_exclusions/toggle",
        json={
            "site_id": data["site_a"],
            "year": 2026,
            "week": 19,
            "day_index": 1,
            "meal": "lunch",
            "alt": "1",
            "diet_type_id": "f09-diet",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["excluded"] is True


def test_real_user_can_mutate_own_weekview_department(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    client.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    _login(client, data)
    payload = {
        "site_id": data["site_a"],
        "department_id": data["department_a"],
        "year": 2026,
        "week": 12,
        "operations": [
            {
                "day_of_week": 1,
                "meal": "lunch",
                "diet_type": "normal",
                "marked": True,
            }
        ],
    }
    response = client.patch(
        "/api/weekview",
        json=payload,
        headers={"If-Match": _weekview_etag(1, data["department_a"])},
    )
    assert response.status_code == 200


def test_real_user_cannot_toggle_foreign_normal_exclusion(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data)
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS normal_exclusions (
                        tenant_id TEXT NOT NULL, site_id TEXT NOT NULL,
                        year INTEGER NOT NULL, week INTEGER NOT NULL,
                        day_index INTEGER NOT NULL, meal TEXT NOT NULL,
                        alt TEXT NOT NULL, diet_type_id TEXT NOT NULL,
                        UNIQUE (tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id)
                    )
                    """
                )
            )
            db.commit()
        finally:
            db.close()
    payload = {
        "site_id": data["site_b"],
        "year": 2026,
        "week": 12,
        "day_index": 1,
        "meal": "lunch",
        "alt": "1",
        "diet_type_id": "f09-diet",
    }
    response = client.post(
        "/api/kitchen/planering/normal_exclusions/toggle",
        json=payload,
    )
    assert response.status_code in (403, 404)
    with app_session.app_context():
        db = get_session()
        try:
            count = db.execute(
                text("SELECT COUNT(*) FROM normal_exclusions WHERE site_id=:site_id"),
                {"site_id": data["site_b"]},
            ).scalar_one()
            assert int(count) == 0
        finally:
            db.close()


def test_real_user_cannot_mark_foreign_department_done(app_session):
    data = _seed_scope(app_session)
    client = app_session.test_client()
    _login(client, data)
    response = client.post(
        "/ui/planera/day/mark_done",
        data={
            "site_id": data["site_a"],
            "date": "2026-03-16",
            "meal": "lunch",
            "department_ids": [data["department_b"]],
        },
        follow_redirects=False,
    )
    assert response.status_code == 403

    allowed = client.post(
        "/ui/planera/day/mark_done",
        data={
            "site_id": data["site_a"],
            "date": "2026-03-16",
            "meal": "lunch",
            "department_ids": [data["department_a"]],
        },
        follow_redirects=False,
    )
    assert allowed.status_code == 302
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(
                text(
                    "SELECT COUNT(*) FROM meal_registrations "
                    "WHERE site_id=:site_id AND department_id=:department_id"
                ),
                {"site_id": data["site_a"], "department_id": data["department_a"]},
            ).scalar_one()
            foreign = db.execute(
                text(
                    "SELECT COUNT(*) FROM meal_registrations "
                    "WHERE department_id=:department_id"
                ),
                {"department_id": data["department_b"]},
            ).scalar_one()
            assert int(row) == 1
            assert int(foreign) == 0
        finally:
            db.close()
