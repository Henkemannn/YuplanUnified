from datetime import date as _date


def _seed_items(app, site_id: str) -> list[str]:
    from core.week_key import week_key_from_date
    from core.remember_to_order_repo import RememberToOrderRepo

    week_key = week_key_from_date(_date.today())
    repo = RememberToOrderRepo()
    items = ["Smor", "Kaffe", "Tomater"]
    with app.app_context():
        for item in items:
            repo.add(site_id, week_key, item, None, "cook")
    return items


def test_admin_dashboard_hides_remember_to_order_without_site(client_admin):
    app = client_admin.application
    leaked_items = _seed_items(app, "site-no-admin")

    with client_admin.session_transaction() as sess:
        sess.pop("site_id", None)

    resp = client_admin.get("/ui/admin", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Välj site för att se listan." in html
    for item in leaked_items:
        assert item not in html


def test_kitchen_dashboard_hides_remember_to_order_without_site(client_cook):
    app = client_cook.application
    leaked_items = _seed_items(app, "site-no-kitchen")

    with client_cook.session_transaction() as sess:
        sess.pop("site_id", None)

    resp = client_cook.get("/ui/kitchen", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Välj site för att se listan." in html
    for item in leaked_items:
        assert item not in html
