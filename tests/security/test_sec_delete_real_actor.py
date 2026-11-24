from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.admin_user_repo import _set_user_site_binding
from core.db import get_session
from core.models import User


@pytest.fixture
def delete_scope_data(app_session):
    password = "RealActorPassw0rd!2026"
    suffix = uuid.uuid4().hex
    site_a = f"sec-delete-a-{suffix}"
    site_b = f"sec-delete-b-{suffix}"
    site_c = f"sec-delete-c-{suffix}"
    admin_email = f"sec-delete-admin-{suffix}@example.test"

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id) VALUES "
                    "(:site_a, 'Security Site A', 1), "
                    "(:site_b, 'Security Site B', 1), "
                    "(:site_c, 'Security Site C', 2)"
                ),
                {"site_a": site_a, "site_b": site_b, "site_c": site_c},
            )
            admin = User(
                tenant_id=1,
                email=admin_email,
                username=admin_email,
                password_hash=generate_password_hash(password),
                role="admin",
                is_active=True,
                auth_version=1,
            )
            db.add(admin)
            db.flush()
            _set_user_site_binding(
                db,
                user_id=int(admin.id),
                tenant_id=1,
                site_id=site_a,
            )
            rows = {}
            for key, tenant_id, site_id in (
                ("own", 1, site_a),
                ("other_site", 1, site_b),
                ("other_tenant", 2, site_c),
                ("null_site", 1, None),
                ("null_other_tenant", 2, None),
            ):
                result = db.execute(
                    text(
                        "INSERT INTO dietary_types "
                        "(tenant_id, site_id, name, semantics, default_select) "
                        "VALUES (:tenant_id, :site_id, :name, 'legacy_bucket', 0)"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "site_id": site_id,
                        "name": f"{key}-{suffix}",
                    },
                )
                rows[key] = int(result.lastrowid)
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS normal_exclusions ("
                    "tenant_id TEXT NOT NULL, site_id TEXT NOT NULL, "
                    "year INTEGER NOT NULL, week INTEGER NOT NULL, "
                    "day_index INTEGER NOT NULL, meal TEXT NOT NULL, "
                    "alt TEXT NOT NULL, diet_type_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO normal_exclusions("
                    "tenant_id, site_id, year, week, day_index, meal, alt, diet_type_id"
                    ") VALUES ('2', :site_id, 2026, 1, 1, 'lunch', '1', :diet_type_id)"
                ),
                {
                    "site_id": site_c,
                    "diet_type_id": str(rows["other_tenant"]),
                },
            )
            db.commit()
            user_id = int(admin.id)
        finally:
            db.close()

    return {
        "admin_email": admin_email,
        "password": password,
        "site_a": site_a,
        "site_b": site_b,
        "user_id": user_id,
        "rows": rows,
    }


def _login_real_actor(client, data):
    response = client.post(
        "/auth/login",
        json={"email": data["admin_email"], "password": data["password"]},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    with client.session_transaction() as session_data:
        assert session_data["user_id"] == data["user_id"]
        assert session_data["tenant_id"] == 1
        assert session_data["site_id"] == data["site_a"]
        assert session_data["site_lock"] is True


def _row_snapshot(diet_id: int):
    db = get_session()
    try:
        return db.execute(
            text("SELECT tenant_id, site_id, name FROM dietary_types WHERE id=:id"),
            {"id": diet_id},
        ).fetchone()
    finally:
        db.close()


def _dependency_count(diet_id: int) -> int:
    db = get_session()
    try:
        return int(
            db.execute(
                text("SELECT COUNT(*) FROM normal_exclusions WHERE diet_type_id=:id"),
                {"id": str(diet_id)},
            ).scalar_one()
        )
    finally:
        db.close()


def test_real_actor_delete_allows_own_site_and_rejects_foreign_rows(
    app_session,
    delete_scope_data,
):
    client = app_session.test_client()
    _login_real_actor(client, delete_scope_data)
    rows = delete_scope_data["rows"]
    dependency_before = _dependency_count(rows["other_tenant"])

    own_before = _row_snapshot(rows["own"])
    response = client.post(f"/ui/admin/specialkost/{rows['own']}/delete")
    assert response.status_code == 302
    assert _row_snapshot(rows["own"]) is None

    for key in ("other_site", "other_tenant", "null_site", "null_other_tenant"):
        before = _row_snapshot(rows[key])
        response = client.post(f"/ui/admin/specialkost/{rows[key]}/delete")
        assert response.status_code in (401, 404)
        assert _row_snapshot(rows[key]) == before
    assert _dependency_count(rows["other_tenant"]) == dependency_before

    assert own_before is not None


def test_real_actor_manipulated_site_and_missing_binding_are_rejected(
    app_session,
    delete_scope_data,
):
    client = app_session.test_client()
    _login_real_actor(client, delete_scope_data)
    own_id = delete_scope_data["rows"]["own"]
    before = _row_snapshot(own_id)

    with client.session_transaction() as session_data:
        session_data["site_id"] = delete_scope_data["site_b"]
    response = client.post(f"/ui/admin/specialkost/{own_id}/delete")
    assert response.status_code == 401
    assert _row_snapshot(own_id) == before

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text("DELETE FROM kitchen_user_sites WHERE user_id=:user_id"),
                {"user_id": delete_scope_data["user_id"]},
            )
            db.commit()
        finally:
            db.close()

    response = client.post(
        "/auth/login",
        json={
            "email": delete_scope_data["admin_email"],
            "password": delete_scope_data["password"],
        },
    )
    assert response.status_code == 403
    payload = response.get_json()
    assert payload is not None
    assert "access_token" not in payload
    assert "refresh_token" not in payload
    with client.session_transaction() as session_data:
        assert session_data.get("user_id") is None
        assert session_data.get("site_id") is None
        assert session_data.get("site_lock") is None

    html_client = app_session.test_client()
    html_response = html_client.post(
        "/auth/login",
        data={
            "email": delete_scope_data["admin_email"],
            "password": delete_scope_data["password"],
        },
        headers={"Accept": "text/html"},
    )
    assert html_response.status_code == 403
    with html_client.session_transaction() as session_data:
        assert session_data.get("user_id") is None
        assert session_data.get("site_id") is None
        assert session_data.get("site_lock") is None

    assert _row_snapshot(own_id) == before


def test_real_actor_invalid_auth_version_and_deactivated_user_are_rejected(
    app_session,
    delete_scope_data,
):
    client = app_session.test_client()
    _login_real_actor(client, delete_scope_data)
    own_id = delete_scope_data["rows"]["own"]
    before = _row_snapshot(own_id)

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text("UPDATE users SET auth_version=auth_version + 1 WHERE id=:user_id"),
                {"user_id": delete_scope_data["user_id"]},
            )
            db.commit()
        finally:
            db.close()

    response = client.post(f"/ui/admin/specialkost/{own_id}/delete")
    assert response.status_code == 401
    assert _row_snapshot(own_id) == before

    client = app_session.test_client()
    _login_real_actor(client, delete_scope_data)
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text("UPDATE users SET is_active=0 WHERE id=:user_id"),
                {"user_id": delete_scope_data["user_id"]},
            )
            db.commit()
        finally:
            db.close()
    response = client.post(f"/ui/admin/specialkost/{own_id}/delete")
    assert response.status_code == 401
    assert _row_snapshot(own_id) == before


def test_real_login_rejects_conflicting_user_and_binding_sites(
    app_session,
    delete_scope_data,
):
    with app_session.app_context():
        db = get_session()
        try:
            user_columns = {
                row[1] for row in db.execute(text("PRAGMA table_info(users)")).fetchall()
            }
            if "site_id" not in user_columns:
                db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT"))
            db.execute(
                text("UPDATE users SET site_id=:site_id WHERE id=:user_id"),
                {
                    "site_id": delete_scope_data["site_a"],
                    "user_id": delete_scope_data["user_id"],
                },
            )
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "UPDATE kitchen_user_sites SET tenant_id=1, site_id=:site_id "
                    "WHERE user_id=:user_id"
                ),
                {
                    "user_id": delete_scope_data["user_id"],
                    "site_id": delete_scope_data["site_b"],
                },
            )
            db.commit()
        finally:
            db.close()

    client = app_session.test_client()
    response = client.post(
        "/auth/login",
        json={
            "email": delete_scope_data["admin_email"],
            "password": delete_scope_data["password"],
        },
    )
    assert response.status_code == 403
    payload = response.get_json()
    assert payload is not None
    assert "access_token" not in payload
    assert "refresh_token" not in payload
    with client.session_transaction() as session_data:
        assert session_data.get("user_id") is None
        assert session_data.get("site_id") is None
        assert session_data.get("site_lock") is None


    html_client = app_session.test_client()
    html_response = html_client.post(
        "/auth/login",
        data={
            "email": delete_scope_data["admin_email"],
            "password": delete_scope_data["password"],
        },
        headers={"Accept": "text/html"},
    )
    assert html_response.status_code == 403
    with html_client.session_transaction() as session_data:
        assert session_data.get("user_id") is None
        assert session_data.get("site_id") is None
        assert session_data.get("site_lock") is None


def test_real_login_accepts_consistent_user_and_binding_sites(
    app_session,
    delete_scope_data,
):
    with app_session.app_context():
        db = get_session()
        try:
            user_columns = {
                row[1] for row in db.execute(text("PRAGMA table_info(users)")).fetchall()
            }
            if "site_id" not in user_columns:
                db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT"))
            db.execute(
                text("UPDATE users SET site_id=:site_id WHERE id=:user_id"),
                {
                    "site_id": delete_scope_data["site_a"],
                    "user_id": delete_scope_data["user_id"],
                },
            )
            db.execute(
                text(
                    "UPDATE kitchen_user_sites SET tenant_id=1, site_id=:site_id "
                    "WHERE user_id=:user_id"
                ),
                {
                    "user_id": delete_scope_data["user_id"],
                    "site_id": delete_scope_data["site_a"],
                },
            )
            db.commit()
        finally:
            db.close()

    _login_real_actor(app_session.test_client(), delete_scope_data)


def test_binding_change_after_login_invalidates_session_and_bearer(
    app_session,
    delete_scope_data,
):
    client = app_session.test_client()
    login_response = client.post(
        "/auth/login",
        json={
            "email": delete_scope_data["admin_email"],
            "password": delete_scope_data["password"],
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.get_json()["access_token"]
    own_id = delete_scope_data["rows"]["own"]
    before = _row_snapshot(own_id)

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "UPDATE kitchen_user_sites SET tenant_id=1, site_id=:site_id "
                    "WHERE user_id=:user_id"
                ),
                {
                    "site_id": delete_scope_data["site_b"],
                    "user_id": delete_scope_data["user_id"],
                },
            )
            db.commit()
        finally:
            db.close()

    session_response = client.post(f"/ui/admin/specialkost/{own_id}/delete")
    assert session_response.status_code == 401
    assert _row_snapshot(own_id) == before

    bearer_client = app_session.test_client()
    bearer_response = bearer_client.post(
        f"/ui/admin/specialkost/{own_id}/delete",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert bearer_response.status_code == 401
    assert _row_snapshot(own_id) == before


def test_ui_delete_rejects_legacy_user_site_conflict_after_login(
    app_session,
    delete_scope_data,
):
    client = app_session.test_client()
    _login_real_actor(client, delete_scope_data)
    own_id = delete_scope_data["rows"]["own"]
    before = _row_snapshot(own_id)

    with app_session.app_context():
        db = get_session()
        try:
            user_columns = {
                row[1] for row in db.execute(text("PRAGMA table_info(users)")).fetchall()
            }
            if "site_id" not in user_columns:
                db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT"))
            db.execute(
                text("UPDATE users SET site_id=:site_id WHERE id=:user_id"),
                {
                    "site_id": delete_scope_data["site_b"],
                    "user_id": delete_scope_data["user_id"],
                },
            )
            db.commit()
        finally:
            db.close()

    response = client.post(f"/ui/admin/specialkost/{own_id}/delete")
    assert response.status_code == 401
    assert _row_snapshot(own_id) == before


def test_forced_password_change_without_binding_stays_account_only(
    app_session,
    delete_scope_data,
):
    password = "ForcedChangePassw0rd!2026"
    new_password = "ForcedChangeNewPassw0rd!2026"
    email = f"forced-change-{uuid.uuid4().hex}@example.test"
    with app_session.app_context():
        db = get_session()
        try:
            user = User(
                tenant_id=1,
                email=email,
                username=email,
                password_hash=generate_password_hash(password),
                role="admin",
                is_active=True,
                auth_version=1,
                must_change_password=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

    client = app_session.test_client()
    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    assert login.get_json()["must_change_password"] is True
    assert client.get("/ui/account").status_code == 200

    blocked = client.post(
        f"/ui/admin/specialkost/{delete_scope_data['rows']['own']}/delete",
        follow_redirects=False,
    )
    assert blocked.status_code in (301, 302, 401)

    changed = client.post(
        "/ui/account/password",
        data={
            "current_password": password,
            "new_password": new_password,
            "confirm_password": new_password,
        },
        follow_redirects=False,
    )
    assert changed.status_code in (301, 302)
    with client.session_transaction() as session_data:
        assert session_data.get("user_id") is None

    relogin = client.post(
        "/auth/login",
        json={"email": email, "password": new_password},
    )
    assert relogin.status_code == 403
