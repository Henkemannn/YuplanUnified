from core import create_app
from core.db import get_session
from core.models import User
from flask import session
from werkzeug.security import generate_password_hash


def test_step1_get_and_post_redirect_step2():
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    client = app.test_client()
    with app.app_context():
        db = get_session()
        try:
            user = db.query(User).filter(User.email == "wizard-sysadmin@example.com").first()
            if not user:
                user = User(
                    tenant_id=1,
                    email="wizard-sysadmin@example.com",
                    username="wizard-sysadmin@example.com",
                    password_hash=generate_password_hash("testpass"),
                    role="superuser",
                    is_active=True,
                    auth_version=1,
                    unit_id=None,
                )
                db.add(user)
                db.commit()
            user_id = int(user.id)
        finally:
            db.close()
    # Establish superuser session
    with client.session_transaction() as s:
        s["user_id"] = user_id
        s["role"] = "superuser"
        s["tenant_id"] = 1
        s["auth_version"] = 1
    r = client.get("/ui/systemadmin/customers/new")
    assert r.status_code == 200
    assert b"Kundnamn" in r.data
    # Post minimal valid data; include csrf_token from session for tests
    with client.session_transaction() as s:
        tok = s.get("CSRF_TOKEN") or "dummy"
    resp = client.post(
        "/ui/systemadmin/customers/new/step1",
        data={
            "csrf_token": tok,
            "tenant_name": "Acme",
            "site_name": "Acme HQ",
            "customer_type": "Kommun",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "/ui/systemadmin/customers/new/contract" in resp.headers.get("Location", "")
