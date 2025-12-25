from flask.testing import FlaskClient


def test_systemadmin_dashboard_renders_for_superuser(app_session, client: FlaskClient):
    # Seed a superuser
    from core.db import get_session
    from core.models import User
    from werkzeug.security import generate_password_hash

    with app_session.app_context():
        db = get_session()
        try:
            # Ensure a superuser exists on tenant 1
            email = "sysadmin@example.com"
            password = "superpass"
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    tenant_id=1,
                    email=email,
                    username=email,
                    password_hash=generate_password_hash(password),
                    role="superuser",
                    full_name="System Admin",
                    is_active=True,
                    unit_id=None,
                )
                db.add(user)
                db.commit()
        finally:
            db.close()

    # 1) Login via /ui/login
    resp = client.post(
        "/ui/login",
        data={"email": "sysadmin@example.com", "password": "superpass"},
        follow_redirects=True,
    )

    # 2) Should end up on /ui/systemadmin/dashboard with 200
    assert resp.status_code == 200
    path_bytes = getattr(resp.request, "path", "/").encode()
    assert b"/ui/systemadmin/dashboard" in path_bytes or b"God morgon" in resp.data or b"SystemAdmin" in resp.data
