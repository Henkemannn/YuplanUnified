import uuid

def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_departments_create_persists_notes_and_redirects_to_edit(app_session, client_admin):
    from core.db import get_session
    from sqlalchemy import text
    # Seed a site and activate in session
    site_id = str(uuid.uuid4())
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id,name,version) VALUES(:i,'TestSite',0)"), {"i": site_id})
            db.commit()
        finally:
            db.close()
    with client_admin.session_transaction() as s:
        s["site_id"] = site_id
    # Create department with notes
    resp = client_admin.post(
        "/ui/admin/departments/new",
        headers=_h("admin"),
        data={
            "name": "CreateNotesDept",
            "resident_count": "12",
            "notes": "Faktaruta: skapas vid create",
        },
        follow_redirects=False,
    )
    # Expect redirect to edit page
    assert resp.status_code in (301, 302)
    loc = resp.headers.get("Location") or ""
    assert "/ui/admin/departments/" in loc and loc.endswith("/edit")
    # Resolve created department id by name and verify notes on detail page
    with app_session.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT id, COALESCE(notes,'') FROM departments WHERE name=:n AND site_id=:s"), {"n": "CreateNotesDept", "s": site_id}).fetchone()
            assert row is not None
            dep_id = str(row[0])
            assert "Faktaruta" in (row[1] or "")
        finally:
            db.close()
    # Notes must appear on the department detail page
    resp_detail = client_admin.get(f"/ui/admin/departments/{dep_id}/detail", headers=_h("admin"))
    assert resp_detail.status_code == 200
    html = resp_detail.get_data(as_text=True)
    assert "Faktaruta" in html or "Faktaruta:" in html
