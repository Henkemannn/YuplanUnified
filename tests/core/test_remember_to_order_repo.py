from datetime import datetime, timedelta, timezone

from core.remember_to_order_repo import RememberToOrderRepo


def test_remember_to_order_ttl_filter(app_session):
    site_id = "site-ttl"
    week_key = "2026-W08"
    now = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)
    repo = RememberToOrderRepo()

    with app_session.app_context():
        item_recent = repo.add(site_id, week_key, "Synlig 1 dag", None, "admin", now=now)
        repo.set_checked(item_recent.id, True, None, site_id, now=now - timedelta(days=1))

        item_old = repo.add(site_id, week_key, "Dolj 3 dagar", None, "admin", now=now)
        repo.set_checked(item_old.id, True, None, site_id, now=now - timedelta(days=3))

        repo.add(site_id, week_key, "Obockad", None, "cook", now=now)

        items = repo.list_visible(site_id, week_key, now=now)
    texts = [it.text for it in items]
    assert "Synlig 1 dag" in texts
    assert "Obockad" in texts
    assert "Dolj 3 dagar" not in texts
