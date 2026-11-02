from flask.testing import FlaskClient
from core.app_factory import create_app
from core.db import get_session
from core.models import User
from sqlalchemy import text
from werkzeug.security import generate_password_hash


def test_systemadmin_sites_page_shows_open_admin_and_hides_ops_links():
    app = create_app({"TESTING": True})
    # Seed one site
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
            db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES('s1','Site 1')"))
            user = db.query(User).filter(User.email == "sites-navigation-sysadmin@example.com").first()
            if not user:
                user = User(
                    tenant_id=1,
                    email="sites-navigation-sysadmin@example.com",
                    username="sites-navigation-sysadmin@example.com",
                    password_hash=generate_password_hash("testpass"),
                    role="superuser",
                    is_active=True,
                    auth_version=1,
                    unit_id=None,
                )
                db.add(user)
                db.flush()
            user_id = int(user.id)
            db.commit()
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    with client.session_transaction() as s:
        s["role"] = "superuser"
        s["user_id"] = user_id
        s["tenant_id"] = 1
        s["auth_version"] = 1
    r = client.get("/ui/admin/system")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # Should include the Open Admin button
    assert "Öppna admin" in html
    # Should not include operational module links in systemadmin context (check main nav only)
    start = html.find('<nav class="main-nav">')
    end = html.find('</nav>', start + 1)
    nav_html = html[start:end] if start != -1 and end != -1 else ""
    assert "Veckovy" not in nav_html
    assert "Avdelningar" not in nav_html
