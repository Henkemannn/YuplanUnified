from flask.testing import FlaskClient
from sqlalchemy import text


def _seed_superuser(app_session):
    from core.db import get_session
    from core.models import User
    from werkzeug.security import generate_password_hash
    with app_session.app_context():
        db = get_session()
        try:
            u = db.query(User).filter(User.email == "sa-binding@example.com").first()
            if not u:
                u = User(tenant_id=1, email="sa-binding@example.com", username="sa-binding@example.com", password_hash=generate_password_hash("superpass"), role="superuser", is_active=True)
                db.add(u)
                db.commit()
        finally:
            db.close()


def _create_tenant(app_session, name="Tenant Bind"):
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


def test_site_admin_creation_sets_site_id_and_login_skips_selector(app_session, client_superuser: FlaskClient):
    # Ensure superuser exists and login
    _seed_superuser(app_session)
    client_superuser.post(
        "/ui/login",
        data={"email": "sa-binding@example.com", "password": "superpass"},
        follow_redirects=True,
    )

    # Create tenant and site with admin
    tid = _create_tenant(app_session)
    resp = client_superuser.post(
        f"/ui/systemadmin/customers/{tid}/sites/create",
        data={
            "site_name": "Bind Site",
            "admin_email": "admin.bind@example.com",
            "admin_password": "Passw0rd!",
            "sf_weekview": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Resolve site_id by name
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM sites WHERE name=:n"), {"n": "Bind Site"}).fetchone()
            assert row is not None
            site_id = str(row[0])
            # Verify admin user's site_id is bound
            urow = db.execute(text("SELECT site_id FROM users WHERE email=:e"), {"e": "admin.bind@example.com"}).fetchone()
            assert urow is not None
            assert str(urow[0]) == site_id
        finally:
            db.close()

    # Logout superuser and login as bound admin
    client_superuser.post("/ui/logout", json={"refresh_token": "dummy"}, follow_redirects=True)
    r_login = client_superuser.post(
        "/ui/login",
        data={"email": "admin.bind@example.com", "password": "Passw0rd!"},
        follow_redirects=False,
    )
    # Expect direct redirect to /ui/admin, not /ui/select-site
    assert r_login.status_code == 302
    loc = r_login.headers.get("Location", "")
    assert "/ui/admin" in loc
    assert "/ui/select-site" not in loc

    # Access /ui/select-site should redirect away for bound admin
    r_sel = client_superuser.get("/ui/select-site", follow_redirects=False)
    assert r_sel.status_code in (302, 303)
    assert "/ui/admin" in (r_sel.headers.get("Location") or "")
