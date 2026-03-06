from sqlalchemy import text


HEADERS = {"X-User-Role": "cook", "X-Tenant-Id": "1"}


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


def test_kitchen_prep_notes_add_and_delete(client_cook):
    app = client_cook.application
    site_id = "site-prep-1"
    _seed_site(app, site_id, "Prep Site")

    with client_cook.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["user_id"] = 101

    add_resp = client_cook.post(
        "/ui/kitchen/prep-notes/add",
        data={"text": "Tina fisk till imorgon"},
        headers=HEADERS,
        follow_redirects=False,
    )
    assert add_resp.status_code in (302, 303)

    list_resp = client_cook.get("/ui/kitchen", headers=HEADERS)
    assert list_resp.status_code == 200
    html = list_resp.data.decode("utf-8")
    assert 'data-testid="prep-notes-card"' in html
    assert "Tina fisk till imorgon" in html

    with app.app_context():
        from core.db import get_session

        db = get_session()
        try:
            row = db.execute(
                text(
                    """
                    SELECT id
                    FROM prep_notes
                    WHERE site_id=:sid AND text=:txt AND is_active=1
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"sid": site_id, "txt": "Tina fisk till imorgon"},
            ).fetchone()
            assert row is not None
            note_id = int(row[0])
        finally:
            db.close()

    del_resp = client_cook.post(
        f"/ui/kitchen/prep-notes/{note_id}/delete",
        headers=HEADERS,
        follow_redirects=False,
    )
    assert del_resp.status_code in (302, 303)

    list_resp_2 = client_cook.get("/ui/kitchen", headers=HEADERS)
    assert list_resp_2.status_code == 200
    html_2 = list_resp_2.data.decode("utf-8")
    assert "Tina fisk till imorgon" not in html_2


def test_kitchen_prep_notes_are_personal_per_user(client_cook):
    app = client_cook.application
    site_id = "site-prep-2"
    _seed_site(app, site_id, "Prep Site 2")

    with app.app_context():
        from core.prep_notes_repo import PrepNotesRepo

        PrepNotesRepo().add(site_id, 201, "Endast min anteckning")

    with client_cook.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["user_id"] = 202

    resp = client_cook.get("/ui/kitchen", headers=HEADERS)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Endast min anteckning" not in html
