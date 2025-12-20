from flask.testing import FlaskClient
from core.app_factory import create_app
from core.db import get_session
from sqlalchemy import text


def test_systemadmin_sites_page_shows_open_admin_and_hides_ops_links():
    app = create_app({"TESTING": True})
    # Seed one site
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
            db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES('s1','Site 1')"))
            db.commit()
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    with client.session_transaction() as s:
        s["role"] = "superuser"
        s["user_id"] = "tester"
        s["tenant_id"] = 1
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
