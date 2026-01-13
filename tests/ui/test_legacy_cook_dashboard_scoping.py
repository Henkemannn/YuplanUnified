"""
Legacy cook dashboard scoping test:
- Seed two sites (A, B); one department only under site A
- With active site B in session, GET /ui/cook should NOT show Dept A
- Switch to site A, GET /ui/cook should show Dept A
"""
import uuid
from sqlalchemy import text


def _h(role: str):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_legacy_cook_dashboard_respects_active_site(app_session, client_admin):
    app = app_session
    site_a = f"site-{uuid.uuid4()}"
    site_b = f"site-{uuid.uuid4()}"
    dept_a = f"dept-{uuid.uuid4()}"

    # Seed two sites and one department only under site A
    from core.db import get_session, create_all
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_a, "name": "Site A"})
            db.execute(text("INSERT INTO sites (id, name, version) VALUES (:id, :name, 0)"), {"id": site_b, "name": "Site B"})
            db.execute(
                text(
                    "INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES (:id, :sid, :name, 'fixed', 12, 0)"
                ),
                {"id": dept_a, "sid": site_a, "name": "Dept A"},
            )
            db.commit()
        finally:
            db.close()

    # Activate site B and verify the legacy cook view does NOT show Dept A
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_b
    r_b = client_admin.get("/ui/cook", headers=_h("cook"))
    assert r_b.status_code == 200
    html_b = r_b.data.decode("utf-8")
    assert "Dept A" not in html_b

    # Switch to site A and verify the legacy cook view shows Dept A
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_a
    r_a = client_admin.get("/ui/cook", headers=_h("cook"))
    assert r_a.status_code == 200
    html_a = r_a.data.decode("utf-8")
    assert "Dept A" in html_a
