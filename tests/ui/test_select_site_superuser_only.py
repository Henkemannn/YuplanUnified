from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import User
from sqlalchemy import text
from werkzeug.security import generate_password_hash


def test_select_site_allowed_for_admin(client_admin, app_session):
    # Ensure schema exists for route rendering
    with app_session.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text("INSERT OR IGNORE INTO sites(id, name, tenant_id) VALUES('s1', 'Site 1', 1)")
            )
            user = db.query(User).filter(User.email == "select-site-admin@example.com").first()
            if not user:
                user = User(
                    tenant_id=1,
                    email="select-site-admin@example.com",
                    username="select-site-admin@example.com",
                    password_hash=generate_password_hash("testpass"),
                    role="admin",
                    is_active=True,
                    auth_version=1,
                )
                db.add(user)
            db.commit()
            user_id = int(user.id)
        finally:
            db.close()
    # Admin should be allowed to access GET /ui/select-site
    # Emulate logged-in admin session
    with client_admin.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = "admin"
        sess["tenant_id"] = 1
        sess["auth_version"] = 1
        sess["site_id"] = "s1"
    r = client_admin.get("/ui/select-site")
    assert r.status_code in (200, 302)
    # POST should be allowed
    r2 = client_admin.post("/ui/select-site", data={"site_id": "s1", "next": "/"})
    assert r2.status_code in (200, 302)
