from datetime import date as _date

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site(site_id: str):
    from sqlalchemy import text
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS sites(
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 0
            )
            """
        ))
        db.execute(text("INSERT OR IGNORE INTO sites(id, name, version) VALUES(:i, 'Plan Site', 0)"), {"i": site_id})
        db.commit()
    finally:
        db.close()


def test_mode_persists_in_links_and_radios(app_session):
    client = app_session.test_client()
    site_id = "site-plan-1"
    _seed_site(site_id)
    today = _date.today()
    year = today.year
    week = today.isocalendar()[1]

    rv = client.get(
        f"/ui/kitchen/planering?site_id={site_id}&mode=normal&year={year}&week={week}&day=0&meal=lunch",
        headers=HEADERS,
    )
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")

    # Mode radios should be present; normal checked
    assert 'name="mode"' in html
    assert 'value="special"' in html
    assert 'value="normal"' in html
    assert ('value="normal"' in html and 'checked' in html)

    # Lunch link should propagate mode=normal
    assert 'meal=lunch' in html
    assert 'mode=normal' in html
