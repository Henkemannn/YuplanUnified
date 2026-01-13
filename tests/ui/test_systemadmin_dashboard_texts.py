from flask.testing import FlaskClient


def test_systemadmin_dashboard_contains_core_texts(app_session, client: FlaskClient):
    # Seed a superuser
    from core.db import get_session
    from core.models import User
    from werkzeug.security import generate_password_hash

    with app_session.app_context():
        db = get_session()
        try:
            email = "sysadmin2@example.com"
            password = "superpass"
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    tenant_id=1,
                    email=email,
                    username=email,
                    password_hash=generate_password_hash(password),
                    role="superuser",
                    full_name="Sys Admin",
                    is_active=True,
                    unit_id=None,
                )
                db.add(user)
                db.commit()
        finally:
            db.close()

    # Login and follow redirects to dashboard
    resp = client.post(
        "/ui/login",
        data={"email": "sysadmin2@example.com", "password": "superpass"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="ignore")
    # Expect key texts in the card/grid view
    assert "Kunder" in html
    assert "Skapa kund" in html
