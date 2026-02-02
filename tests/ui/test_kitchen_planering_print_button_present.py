from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site():
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name, version) VALUES('site-plan-1','Plan Site',0)"))
        db.commit()
    finally:
        db.close()


def test_print_button_present(app_session):
    client = app_session.test_client()
    _seed_site()
    rv = client.get("/ui/kitchen/planering?site_id=site-plan-1", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert 'Skriv ut' in html
