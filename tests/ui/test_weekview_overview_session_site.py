from sqlalchemy import text
from core.db import get_session
from core.models import User
from tests._auth_site_helpers import login_bound_user


def test_weekview_overview_derives_site_from_session(app_session, client_admin):
    # Arrange: ensure session already has a bound site via client_admin fixture
    # Also set minimal auth context required by route (role + tenant)
    site_id = "weekview-session-site"
    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text("INSERT OR IGNORE INTO sites(id, name, tenant_id, version) VALUES(:id, 'Weekview Site', 1, 0)"),
                {"id": site_id},
            )
            db.commit()
        finally:
            db.close()
    login_bound_user(client_admin, site_id=site_id, email="weekview-session-site@example.test")
    # Act: request overview WITHOUT site_id in query
    resp = client_admin.get("/ui/weekview_overview?year=2026&week=4")

    # Assert: OK and page structure rendered (header + day cells)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Stable markers: title contains week number and container for day cells exists
    assert "Weekview Översikt – Vecka 4" in html
    assert "weekview-overview-day-cell" in html
