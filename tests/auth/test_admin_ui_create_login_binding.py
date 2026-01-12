from flask.testing import FlaskClient
from sqlalchemy import text


def _seed_superuser(app_session):
    from core.db import get_session
    from core.models import User
    from werkzeug.security import generate_password_hash
    with app_session.app_context():
        db = get_session()
        try:
            u = db.query(User).filter(User.email == "sa-ui-create@example.com").first()
            if not u:
                u = User(
                    tenant_id=1,
                    email="sa-ui-create@example.com",
                    username="sa-ui-create@example.com",
                    password_hash=generate_password_hash("superpass"),
                    role="superuser",
                    is_active=True,
                )
                db.add(u)
                db.commit()
        finally:
            db.close()


def _create_tenant(app_session, name="Tenant UI Create"):
    from core.db import get_session
    from core.models import Tenant
    with app_session.app_context():
        db = get_session()
        try:
            t = Tenant(name=name)
            db.add(t)
            db.commit()
            return t.id
        finally:
            db.close()


def test_admin_ui_create_user_login_succeeds_and_binds_site(app_session, client_superuser: FlaskClient):
    # Ensure superuser exists and login
    _seed_superuser(app_session)
    client_superuser.post(
        "/ui/login",
        data={"email": "sa-ui-create@example.com", "password": "superpass"},
        follow_redirects=True,
    )

    # Create tenant and a site (wizard route)
    tid = _create_tenant(app_session)
    resp = client_superuser.post(
        f"/ui/systemadmin/customers/{tid}/sites/create",
        data={
            "site_name": "UI Create Site",
            "admin_email": "first.admin@example.com",
            "admin_password": "Passw0rd!",
            "sf_weekview": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Resolve site_id by name and switch site context
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM sites WHERE name=:n"), {"n": "UI Create Site"}).fetchone()
            assert row is not None
            site_id = str(row[0])
        finally:
            db.close()

    client_superuser.get(f"/ui/systemadmin/switch-site/{site_id}", follow_redirects=True)

    # Create a new admin via unified admin UI
    new_email = "babianen@lindgården.se"
    new_password = "Test1234"
    resp_new = client_superuser.post(
        "/ui/admin/users/new",
        data={
            "username": new_email,
            "email": new_email,
            "full_name": "Babianen Admin",
            "password": new_password,
            "role": "admin",
        },
        follow_redirects=True,
    )
    assert resp_new.status_code == 200

    # Verify user.site_id is bound to the active site
    with app_session.app_context():
        db = get_session()
        try:
            # Use canonicalized email for lookup (IDNA punycode domain)
            from core.ident import canonicalize_identifier
            ce = canonicalize_identifier(new_email)
            urow = db.execute(text("SELECT site_id, password_hash FROM users WHERE email=:e"), {"e": ce}).fetchone()
            assert urow is not None
            assert str(urow[0]) == site_id
            # Password hash should be non-empty and not the placeholder
            assert isinstance(urow[1], str) and len(urow[1]) > 10 and urow[1] != "!"
        finally:
            db.close()

    # Logout and login as newly created admin
    client_superuser.post("/ui/logout", json={"refresh_token": "dummy"}, follow_redirects=True)
    r_login = client_superuser.post(
        "/ui/login",
        data={"email": new_email, "password": new_password},
        follow_redirects=False,
    )
    # Expect direct redirect to /ui/admin, not /ui/select-site
    assert r_login.status_code == 302
    loc = r_login.headers.get("Location", "")
    assert "/ui/admin" in loc
    assert "/ui/select-site" not in loc
