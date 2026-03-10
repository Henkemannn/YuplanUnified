import uuid

from sqlalchemy import text


def _h(role: str) -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_new_department_form_shows_residence_controls(client_admin):
    resp = client_admin.get("/ui/admin/departments/new", headers=_h("admin"))
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'name="residence_id"' in html
    assert "Lägg till boende" in html
    assert "residence-create-modal" in html


def test_create_residence_from_modal_redirects_with_selection(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())

    from core.db import create_all, get_session

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.post(
        "/ui/admin/residences/new",
        headers=_h("admin"),
        data={"name": "Boende Sol"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers.get("Location") or ""
    assert "/ui/admin/departments/new?residence_id=" in location


def test_create_department_requires_residence_selection(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())

    from core.db import create_all, get_session

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={"name": "Avd A", "resident_count": "12"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Boende måste väljas" in html


def test_create_department_persists_residence_id(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    residence_id = str(uuid.uuid4())

    from core.db import create_all, get_session

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.execute(
                text("INSERT INTO residences (id, site_id, name) VALUES(:id, :sid, :name)"),
                {"id": residence_id, "sid": site_id, "name": "Boende A"},
            )
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={"name": "Avd B", "resident_count": "20", "residence_id": residence_id},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        db = get_session()
        try:
            row = db.execute(
                text("SELECT residence_id FROM departments WHERE site_id=:sid AND name=:name"),
                {"sid": site_id, "name": "Avd B"},
            ).fetchone()
        finally:
            db.close()

    assert row is not None
    assert row[0] == residence_id


def test_edit_form_old_department_without_residence_still_renders(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())

    from core.db import create_all, get_session

    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_id, "name": "TestSite"})
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES(:id, :sid, :name, 'fixed', 15, 0)"
                ),
                {"id": dept_id, "sid": site_id, "name": "Legacy Dept"},
            )
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    resp = client_admin.get(f"/ui/admin/departments/{dept_id}/edit", headers=_h("admin"))
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Legacy Dept" in html
