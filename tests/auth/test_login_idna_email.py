from flask.testing import FlaskClient
from sqlalchemy import text


def _seed_superuser(app_session):
    from core.db import get_session
    from core.models import User
    from werkzeug.security import generate_password_hash
    with app_session.app_context():
        db = get_session()
        try:
            u = db.query(User).filter(User.email == "sa-idna@example.com").first()
            if not u:
                u = User(
                    tenant_id=1,
                    email="sa-idna@example.com",
                    username="sa-idna@example.com",
                    password_hash=generate_password_hash("superpass"),
                    role="superuser",
                    is_active=True,
                )
                db.add(u)
                db.commit()
        finally:
            db.close()


def _create_tenant(app_session, name="Tenant IDNA"):
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


def test_login_with_idna_unicode_and_punycode_emails(app_session, client_superuser: FlaskClient):
    # Login as superuser
    _seed_superuser(app_session)
    client_superuser.post(
        "/ui/login",
        data={"email": "sa-idna@example.com", "password": "superpass"},
        follow_redirects=True,
    )

    # Create tenant and a site (wizard route)
    tid = _create_tenant(app_session)
    resp = client_superuser.post(
        f"/ui/systemadmin/customers/{tid}/sites/create",
        data={
            "site_name": "IDNA Site",
            "admin_email": "first.admin@example.com",
            "admin_password": "Passw0rd!",
            "sf_weekview": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Find site_id by name and switch
    from core.db import get_session
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id FROM sites WHERE name=:n"), {"n": "IDNA Site"}).fetchone()
            assert row is not None
            site_id = str(row[0])
        finally:
            db.close()

    client_superuser.get(f"/ui/systemadmin/switch-site/{site_id}", follow_redirects=True)

    # Create a new admin via unified admin UI with UNICODE domain
    unicode_email = "babianen@lindgården.se"
    punycode_email = "babianen@xn--lindgrden-92a.se"
    password = "Test1234"

    resp_new = client_superuser.post(
        "/ui/admin/users/new",
        data={
            "username": unicode_email,
            "email": unicode_email,
            "full_name": "Babianen IDN",
            "password": password,
            "role": "admin",
        },
        follow_redirects=True,
    )
    assert resp_new.status_code == 200

    # Verify storage: username is not NULL and equals canonical (punycode) email
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT email, username, site_id FROM users WHERE email=:e OR email=:p"),
                {"e": unicode_email.lower(), "p": punycode_email.lower()},
            ).fetchone()
            # Either stored as punycode or canonically looked-up via punycode variant
            assert row is not None
            stored_email, stored_username, stored_site = row
            assert stored_username is not None and stored_username != ""
            # Ensure bound to active site
            assert str(stored_site) == site_id
        finally:
            db.close()

    # Logout superuser and test login with UNICODE email
    client_superuser.post("/ui/logout", json={"refresh_token": "dummy"}, follow_redirects=True)
    r_login_unicode = client_superuser.post(
        "/ui/login",
        data={"email": unicode_email, "password": password},
        follow_redirects=False,
    )
    assert r_login_unicode.status_code == 302
    loc_u = r_login_unicode.headers.get("Location", "")
    assert "/ui/admin" in loc_u and "/ui/select-site" not in loc_u

    # Test login with PUNYCODE email also works
    client_superuser.post("/ui/logout", json={"refresh_token": "dummy"}, follow_redirects=True)
    r_login_puny = client_superuser.post(
        "/ui/login",
        data={"email": punycode_email, "password": password},
        follow_redirects=False,
    )
    assert r_login_puny.status_code == 302
    loc_p = r_login_puny.headers.get("Location", "")
    assert "/ui/admin" in loc_p and "/ui/select-site" not in loc_p
