from flask.testing import FlaskClient
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session


def _h(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_weekview_shows_error_on_tenant_site_mismatch():
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    client: FlaskClient = app.test_client()
    db = get_session()

    try:
        # Ensure sites table and create a site with tenant_id=2
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT)"))
        cols = {r[1] for r in db.execute(text("PRAGMA table_info('sites')")).fetchall()}
        if "tenant_id" not in cols:
            db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER"))
        db.execute(text("INSERT OR REPLACE INTO sites(id,name,tenant_id) VALUES('mismatch-site','Mismatch',2)"))
        db.commit()
    finally:
        db.close()

    # Session bound to tenant 1 but site is owned by tenant 2
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "admin"
        sess["tenant_id"] = 1
        sess["site_id"] = "mismatch-site"
        sess["site_lock"] = True

    r = client.get("/ui/weekview?site_id=mismatch-site&year=2026&week=8", headers=_h("admin"))
    # Expect explicit 403 and Swedish error message
    assert r.status_code == 403
    html = r.get_data(as_text=True)
    assert "tillhör en annan tenant" in html
