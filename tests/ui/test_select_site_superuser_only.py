from core.db import create_all, get_session
from core.admin_user_repo import _resolve_user_site_id
from sqlalchemy import text
from tests._auth_site_helpers import login_bound_user


def test_bound_admin_cannot_switch_to_another_site(client_admin, app_session):
    # Ensure schema exists for route rendering
    with app_session.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text("INSERT OR IGNORE INTO sites(id, name, tenant_id) VALUES('s1', 'Site 1', 1)")
            )
            db.execute(
                text("INSERT OR IGNORE INTO sites(id, name, tenant_id) VALUES('s2', 'Site 2', 1)")
            )
            db.commit()
        finally:
            db.close()
    user_id = login_bound_user(
        client_admin,
        site_id="s1",
        role="admin",
        email="select-site-bound-admin@example.com",
        password="TestPassw0rd!2026",
    )
    r = client_admin.get("/ui/select-site")
    assert r.status_code in (302, 401, 403)
    if r.status_code == 302:
        assert (r.headers.get("Location") or "") in ("/ui/admin", "/auth/login")
    r2 = client_admin.post("/ui/select-site", data={"site_id": "s2", "next": "/"})
    assert r2.status_code in (302, 401, 403)
    if r2.status_code == 302:
        assert (r2.headers.get("Location") or "") in ("/ui/admin", "/auth/login")
    with client_admin.session_transaction() as session:
        assert session.get("site_id") == "s1"
    with app_session.app_context():
        db = get_session()
        try:
            assert _resolve_user_site_id(db, user_id=user_id, tenant_id=1) == "s1"
            db.execute(
                text(
                    "INSERT INTO departments "
                    "(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES ('site-b-secret-department', 's2', 'Site B Secret Department', 'fixed', 7, 0)"
                )
            )
            db.commit()
        finally:
            db.close()
    protected = client_admin.get("/ui/admin/departments?site_id=s2")
    assert protected.status_code == 200
    assert "Site B Secret Department" not in protected.get_data(as_text=True)
