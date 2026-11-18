from sqlalchemy import text

from core.db import get_session
from tests.test_admin_user_target_authorization import _create_user, _login, _seed_scope


def _list_response(app_session, email):
    client = app_session.test_client()
    _login(client, email)
    response = client.get("/ui/admin/users")
    assert response.status_code == 200
    return response.data.decode("utf-8")


def test_admin_user_list_is_filtered_by_verified_site(app_session):
    data = _seed_scope(app_session)
    site_a_user = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b03-site-a@example.com",
        role="staff",
        site_id=data["site_a"],
    )
    site_a2_user = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b03-site-a2@example.com",
        role="staff",
        site_id=data["site_a2"],
    )
    cross_tenant_user = _create_user(
        app_session,
        tenant_id=data["tenant_b"],
        email="08b03-site-b@example.com",
        role="staff",
        site_id=data["site_b"],
    )
    unbound_user = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b03-unbound@example.com",
        role="staff",
    )
    conflicting_user = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b03-conflicting@example.com",
        role="staff",
        site_id=data["site_a"],
    )
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode) "
                    "VALUES('08b03-conflict-dept', :sid, 'Conflict department', 'manual')"
                ),
                {"sid": data["site_a2"]},
            )
            db.execute(
                text("UPDATE users SET department_id='08b03-conflict-dept' WHERE id=:uid"),
                {"uid": conflicting_user},
            )
            db.commit()
        finally:
            db.close()

    html = _list_response(app_session, data["admin_a"])
    assert "08b03-site-a@example.com" in html
    assert data["admin_same"] in html
    assert "08b03-site-a2@example.com" not in html
    assert "08b03-site-b@example.com" not in html
    assert "08b03-unbound@example.com" not in html
    assert "08b03-conflicting@example.com" not in html
    assert data["superuser"] not in html

    same_site_html = _list_response(app_session, data["admin_same"])
    assert ("08b03-site-a@example.com" in same_site_html) == (
        "08b03-site-a@example.com" in html
    )
    assert site_a_user
    assert site_a2_user
    assert cross_tenant_user
    assert unbound_user


def test_admin_user_list_accepts_users_site_id_schema(app_session, request):
    data = _seed_scope(app_session)
    site_column_user = _create_user(
        app_session,
        tenant_id=data["tenant_a"],
        email="08b03-site-column@example.com",
        role="staff",
    )
    with app_session.app_context():
        db = get_session()
        try:
            columns = {
                str(row[1])
                for row in db.execute(text("PRAGMA table_info(users)")).fetchall()
            }
            added_column = "site_id" not in columns
            if "site_id" not in columns:
                db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT"))
            db.execute(
                text("UPDATE users SET site_id=:sid WHERE id=:uid"),
                {"sid": data["site_a"], "uid": site_column_user},
            )
            db.commit()
        finally:
            db.close()

    if added_column:
        def cleanup_site_column():
            with app_session.app_context():
                db = get_session()
                try:
                    db.execute(text("ALTER TABLE users DROP COLUMN site_id"))
                    db.commit()
                finally:
                    db.close()

        request.addfinalizer(cleanup_site_column)

    html = _list_response(app_session, data["admin_a"])
    assert "08b03-site-column@example.com" in html
