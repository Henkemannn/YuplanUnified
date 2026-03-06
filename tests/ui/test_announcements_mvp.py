from datetime import date, timedelta

from sqlalchemy import text


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
COOK_HEADERS = {"X-User-Role": "cook", "X-Tenant-Id": "1"}


def _seed_site(app, site_id: str, name: str) -> None:
    with app.app_context():
        from core.db import get_session

        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(
                text("INSERT OR REPLACE INTO sites(id, name, version) VALUES(:id, :name, 0)"),
                {"id": site_id, "name": name},
            )
            db.commit()
        finally:
            db.close()


def test_admin_announcements_create_and_show_on_admin_dashboard(client_admin):
    app = client_admin.application
    site_id = "site-ann-admin"
    _seed_site(app, site_id, "Ann Site Admin")

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    event_date = (date.today() + timedelta(days=1)).isoformat()
    post_resp = client_admin.post(
        "/ui/admin/announcements",
        data={
            "event_date": event_date,
            "event_time": "09:30",
            "message": "Ring anh\u00f6riga om allergi",
            "show_on_kitchen_dashboard": "on",
        },
        headers=ADMIN_HEADERS,
        follow_redirects=False,
    )
    assert post_resp.status_code in (302, 303)

    list_resp = client_admin.get("/ui/admin/announcements", headers=ADMIN_HEADERS)
    assert list_resp.status_code == 200
    list_html = list_resp.data.decode("utf-8")
    assert "Nytt meddelande" in list_html
    assert "Ring anh\u00f6riga om allergi" in list_html
    assert "Visas i k\u00f6ksportalen" in list_html

    dashboard_resp = client_admin.get("/ui/admin", headers=ADMIN_HEADERS)
    assert dashboard_resp.status_code == 200
    dashboard_html = dashboard_resp.data.decode("utf-8")
    assert 'data-testid="admin-announcements-card"' in dashboard_html
    assert "Ring anh\u00f6riga om allergi" in dashboard_html
    assert "/ui/admin/announcements" in dashboard_html


def test_kitchen_dashboard_only_shows_kitchen_flagged_announcements(client_cook):
    app = client_cook.application
    site_id = "site-ann-kitchen"
    _seed_site(app, site_id, "Ann Site Kitchen")

    with app.app_context():
        from core.announcements_repo import AnnouncementsRepo

        repo = AnnouncementsRepo()
        repo.create(
            site_id=site_id,
            message="Syns i k\u00f6k",
            event_date=date.today(),
            event_time=None,
            show_on_kitchen_dashboard=True,
            created_by_user_id=None,
        )
        repo.create(
            site_id=site_id,
            message="Endast admin",
            event_date=date.today(),
            event_time=None,
            show_on_kitchen_dashboard=False,
            created_by_user_id=None,
        )

    with client_cook.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_cook.get("/ui/kitchen", headers=COOK_HEADERS)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'data-testid="kitchen-announcements-card"' in html
    assert "Syns i k\u00f6k" in html
    assert "Endast admin" not in html


def test_admin_can_delete_announcement(client_admin):
    app = client_admin.application
    site_id = "site-ann-delete"
    _seed_site(app, site_id, "Ann Site Delete")

    with app.app_context():
        from core.announcements_repo import AnnouncementsRepo

        repo = AnnouncementsRepo()
        item_id = repo.create(
            site_id=site_id,
            message="Ta bort mig",
            event_date=date.today(),
            event_time=None,
            show_on_kitchen_dashboard=False,
            created_by_user_id=None,
        )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    delete_resp = client_admin.post(
        f"/ui/admin/announcements/{item_id}/delete",
        headers=ADMIN_HEADERS,
        follow_redirects=False,
    )
    assert delete_resp.status_code in (302, 303)

    list_resp = client_admin.get("/ui/admin/announcements", headers=ADMIN_HEADERS)
    assert list_resp.status_code == 200
    html = list_resp.data.decode("utf-8")
    assert "Ta bort mig" not in html


def test_admin_can_edit_announcement_inline(client_admin):
    app = client_admin.application
    site_id = "site-ann-edit"
    _seed_site(app, site_id, "Ann Site Edit")

    with app.app_context():
        from core.announcements_repo import AnnouncementsRepo

        repo = AnnouncementsRepo()
        item_id = repo.create(
            site_id=site_id,
            message="Gammalt meddelande",
            event_date=date.today(),
            event_time=None,
            show_on_kitchen_dashboard=False,
            created_by_user_id=None,
        )

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    prefill_resp = client_admin.get(f"/ui/admin/announcements?edit={item_id}", headers=ADMIN_HEADERS)
    assert prefill_resp.status_code == 200
    prefill_html = prefill_resp.data.decode("utf-8")
    assert "Redigera meddelande" in prefill_html
    assert f'value="{item_id}"' in prefill_html

    new_date = (date.today() + timedelta(days=2)).isoformat()
    update_resp = client_admin.post(
        "/ui/admin/announcements",
        data={
            "announcement_id": str(item_id),
            "event_date": new_date,
            "event_time": "13:15",
            "message": "Uppdaterat meddelande",
            "show_on_kitchen_dashboard": "on",
        },
        headers=ADMIN_HEADERS,
        follow_redirects=False,
    )
    assert update_resp.status_code in (302, 303)

    list_resp = client_admin.get("/ui/admin/announcements", headers=ADMIN_HEADERS)
    assert list_resp.status_code == 200
    html = list_resp.data.decode("utf-8")
    assert "Uppdaterat meddelande" in html
    assert "13:15" in html
    assert "Redigera" in html
    assert "Ta bort" in html

    kitchen_resp = client_admin.get("/ui/kitchen", headers={"X-User-Role": "cook", "X-Tenant-Id": "1"})
    assert kitchen_resp.status_code == 200
    kitchen_html = kitchen_resp.data.decode("utf-8")
    assert "Uppdaterat meddelande" in kitchen_html
